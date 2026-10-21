"""Use unchanged v14 pipeline, but put its output schema in the actual prompt."""
import json
import runpy
import sys
from pathlib import Path

from app.evaluation import source_documents

Base = source_documents.MeasuredClient

class SchemaClient(Base):
    def post(self, url, *, json):
        if 'prompt' in json:
            payload = __import__('json').loads(json['prompt'])
            json = {**json, 'prompt': __import__('json').dumps(
                {**payload, 'output_schema': json['format']}, ensure_ascii=False)}
        return super().post(url, json=json)

source_documents.MeasuredClient = SchemaClient
target = Path(sys.argv[1])
runpy.run_path('/private/tmp/noye-phase8-20261014/support-holdout.py', run_name='__main__')
data = json.loads(target.read_text())
data['measurement_change'] = __doc__
data['calibration_note'] = 'The former holdout is now a known calibration set. A later unseen set and whole documents are required before acceptance.'
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
