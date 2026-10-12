import { AppShell } from "@/components/app-shell";
import { FolderWorkspace } from "@/components/folder-workspace";

export default function FoldersPage() {
  return <AppShell current="Folders" title="Knowledge folders" description="Connected originals, processing and filing." workspace>
    <div className="min-h-0 flex-1 overflow-y-auto"><FolderWorkspace /></div>
  </AppShell>;
}
