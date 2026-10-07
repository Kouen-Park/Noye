import { AppShell } from "@/components/app-shell";
import { FolderWorkspace } from "@/components/folder-workspace";

export default function FoldersPage() {
  return <AppShell current="Folders"><h1 className="text-[27px]">Knowledge folders</h1>
    <FolderWorkspace />
  </AppShell>;
}
