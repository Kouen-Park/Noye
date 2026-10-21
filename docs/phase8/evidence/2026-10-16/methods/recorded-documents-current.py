"""Use the current production acceptance CLI with exact synthetic model inputs retained."""
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
