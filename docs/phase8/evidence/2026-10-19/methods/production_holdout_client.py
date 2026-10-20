"""Capture exact production requests without executing the CLI holdout script."""
from app.evaluation.source_documents import MeasuredClient


class RecordedClient(MeasuredClient):
    def post(self, url, *, json):
        before = len(self.calls)
        try:
            return super().post(url, json=json)
        finally:
            if len(self.calls) > before:
                self.calls[-1]['request'] = json
