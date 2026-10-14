//! WebKit print completion must be asynchronous: its page preparation needs the
//! main event loop. Only AppKit's completion callback can publish the final PDF.
use std::{cell::RefCell, path::PathBuf, sync::mpsc::SyncSender};

use objc2::{
    define_class, msg_send,
    rc::Retained,
    runtime::{Bool, ProtocolObject},
    AnyThread, DefinedClass, MainThreadMarker, MainThreadOnly,
};
use objc2_app_kit::{
    NSPrintAllPages, NSPrintInfo, NSPrintJobSavingURL, NSPrintOperation, NSPrintSaveJob, NSWindow,
};
use objc2_foundation::{NSNumber, NSObject, NSObjectProtocol, NSSize, NSString, NSURL};
use objc2_web_kit::WKWebView;

type Reply = SyncSender<Result<(), String>>;

struct Output {
    directory: PathBuf,
    destination: PathBuf,
    reply: Reply,
    // Keep the operation alive through the asynchronous callback.
    _operation: Retained<NSPrintOperation>,
}
impl Drop for Output {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.directory);
    }
}
impl Output {
    fn publish(&self, successful: bool) -> Result<(), String> {
        if !successful {
            return Err("Could not render the PDF.".into());
        }
        use std::io::Read;
        let output = self.directory.join("document.pdf");
        let file = std::fs::File::open(&output).map_err(|_| "The PDF was not created")?;
        let mut header = [0; 5];
        (&file)
            .read_exact(&mut header)
            .map_err(|_| "The PDF was incomplete")?;
        if &header != b"%PDF-" {
            return Err("The rendered file was not a PDF".into());
        }
        file.sync_all()
            .map_err(|_| "Could not finish writing the PDF")?;
        crate::exports::publish_file(&output, &self.destination).map_err(|_| {
            "Could not save PDF. Choose a new filename and check folder permissions.".into()
        })
    }
}

struct Completion {
    output: RefCell<Option<Output>>,
}

define_class!(
    // NSObject has no additional subclassing requirements. The delegate and
    // its print operation are created and accessed only on the main thread.
    #[unsafe(super(NSObject))]
    #[thread_kind = MainThreadOnly]
    #[ivars = Completion]
    struct PdfCompletion;

    unsafe impl NSObjectProtocol for PdfCompletion {}

    impl PdfCompletion {
        // AppKit's documented didRun selector takes the operation, BOOL success,
        // and the opaque context pointer (unused here).
        #[unsafe(method(printOperationDidRun:success:contextInfo:))]
        fn finished(&self, _operation: &NSPrintOperation, success: Bool, _context: *mut std::ffi::c_void) {
            // Retain self until after its callback returns, then release the
            // global owner. No delegate pointer outlives the print operation.
            let _hold = ACTIVE.with(|active| active.borrow().as_ref().cloned());
            if let Some(output) = self.ivars().output.borrow_mut().take() {
                let result = output.publish(success.as_bool());
                let _ = output.reply.send(result);
            }
            ACTIVE.with(|active| {
                if let Some(completion) = active.borrow_mut().take() {
                    // AppKit's enclosing autorelease pool releases the last
                    // owner after the Objective-C callback has returned.
                    let _ = Retained::autorelease_ptr(completion);
                }
            });
        }
    }
);

thread_local! {
    // ExportGuard permits one operation. Keep its delegate alive until AppKit
    // completes; an ordinary local variable would be dropped on dispatch return.
    static ACTIVE: RefCell<Option<Retained<PdfCompletion>>> = const { RefCell::new(None) };
}

pub(crate) fn begin(
    view: *mut std::ffi::c_void,
    window: *mut std::ffi::c_void,
    destination: PathBuf,
    reply: Reply,
) -> Result<(), String> {
    let marker = MainThreadMarker::new().ok_or("PDF export requires the main thread")?;
    let directory = destination
        .parent()
        .ok_or("Choose a destination folder")?
        .join(format!(".noye-pdf-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&directory).map_err(|_| "Could not create the PDF staging folder")?;
    let output = directory.join("document.pdf");
    // Tauri supplies the actual WKWebView/NSWindow on its main-thread callback.
    // A fresh copy avoids changing shared print preferences; the fixed positive
    // A4 metrics work without a configured printer. The existing print CSS is used.
    unsafe {
        let view: &WKWebView = &*view.cast();
        let window: &NSWindow = &*window.cast();
        let defaults = NSPrintInfo::sharedPrintInfo();
        let info = NSPrintInfo::initWithDictionary(NSPrintInfo::alloc(), &defaults.dictionary());
        info.setPaperSize(NSSize::new(595.28, 841.89));
        info.setTopMargin(36.0);
        info.setBottomMargin(36.0);
        info.setLeftMargin(36.0);
        info.setRightMargin(36.0);
        info.setJobDisposition(NSPrintSaveJob);
        info.setSelectionOnly(false);
        info.dictionary().setObject_forKey(
            &NSNumber::numberWithBool(true),
            ProtocolObject::from_ref(NSPrintAllPages),
        );
        let url = NSURL::fileURLWithPath(&NSString::from_str(&output.to_string_lossy()));
        info.dictionary()
            .setObject_forKey(&url, ProtocolObject::from_ref(NSPrintJobSavingURL));
        let operation = view.printOperationWithPrintInfo(&info);
        operation.setShowsPrintPanel(false);
        operation.setShowsProgressPanel(false);
        operation.setCanSpawnSeparateThread(true);
        let allocated = PdfCompletion::alloc(marker).set_ivars(Completion {
            output: RefCell::new(Some(Output {
                directory,
                destination,
                reply,
                _operation: operation.clone(),
            })),
        });
        let completion: Retained<PdfCompletion> = msg_send![super(allocated), init];
        ACTIVE.with(|active| {
            active.replace(Some(completion.clone()));
        });
        operation.runOperationModalForWindow_delegate_didRunSelector_contextInfo(
            window,
            Some(&completion),
            Some(objc2::sel!(printOperationDidRun:success:contextInfo:)),
            std::ptr::null_mut(),
        );
    }
    Ok(())
}
