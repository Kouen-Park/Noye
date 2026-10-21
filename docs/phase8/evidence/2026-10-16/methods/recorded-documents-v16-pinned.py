"""Run the existing synthetic acceptance CLI, retaining exact model input too."""
import sys

# Remaining v16 subprocesses stay on this immutable committed snapshot while
# the workspace proceeds to the reference-selection fix. The already-running
# v16 process loaded the same modules before workspace edits.
sys.path.insert(0, '/private/tmp/noye-phase8-20261016/v16-code/backend')
from app.evaluation import source_documents as evaluation


class RecordedClient(evaluation.MeasuredClient):
    def post(self, url, *, json):
        before = len(self.calls)
        try:
            return super().post(url, json=json)
        finally:
            if len(self.calls) > before:
                self.calls[-1]["request"] = json


evaluation.MeasuredClient = RecordedClient
evaluation.main()
