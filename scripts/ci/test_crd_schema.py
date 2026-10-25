"""Offline provenance and real kubeconform regressions for operator resources."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

from crd_schema import convert

CI = Path(__file__).resolve().parent
ROOT = CI.parents[1]
CASES = (
    ('cert-manager', 'cert-manager-1.21.2.yaml', 'Certificate',
     'overlays/dev/certificate.yaml', 'dnsNames', 'not-an-array'),
    ('cloudnative-pg', 'cnpg-1.30.1.yaml', 'Cluster',
     'components/cloudnative-pg/cluster.yaml', 'instances', 'not-an-integer'),
    ('barman-cloud', 'barman-cloud-0.15.1.yaml', 'ObjectStore',
     'components/r2-backup/objectstore.yaml', 'retentionPolicy', 7),
)


class SchemaProvenanceTests(unittest.TestCase):
    def test_schemas_match_vendored_served_versions_and_resources(self):
        for operator, release, kind, resource, _, _ in CASES:
            with self.subTest(kind=kind):
                bundle = ROOT / 'kubernetes/platform' / operator / 'upstream' / release
                crd = next(doc for doc in yaml.safe_load_all(bundle.read_text())
                           if doc and doc.get('kind') == 'CustomResourceDefinition'
                           and doc['spec']['names']['kind'] == kind)
                manifest = yaml.safe_load((ROOT / 'kubernetes/apps/liora' / resource).read_text())
                group, version = manifest['apiVersion'].split('/')
                self.assertEqual(group, crd['spec']['group'])
                name, expected = convert(crd, version)
                self.assertEqual(json.loads((CI / name).read_text()), expected)
                self.assertIs(expected['additionalProperties'], False)
                self.assertIs(expected['properties']['spec']['additionalProperties'], False)


class KubeconformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executable = shutil.which('kubeconform')
        if cls.executable is None:
            # CI installs the pinned executable before running this suite.
            raise RuntimeError('kubeconform is required for CRD regression tests')

    def validate(self, manifest):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'resource.yaml'
            path.write_text(yaml.safe_dump(manifest))
            # Only local schemas: these tests never download standard schemas.
            return subprocess.run([
                self.executable, '-strict', '-summary', '-schema-location',
                str(CI / 'crd-{{.Group}}-{{.ResourceKind}}-{{.ResourceAPIVersion}}.json'),
                str(path),
            ], capture_output=True, text=True)

    def test_real_resources_pass_and_malformed_resources_fail(self):
        for _, _, kind, resource, field, invalid in CASES:
            manifest = yaml.safe_load((ROOT / 'kubernetes/apps/liora' / resource).read_text())
            with self.subTest(kind=kind, case='valid'):
                result = self.validate(manifest)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for case in ('unknown-field', 'wrong-type', 'missing-schema'):
                with self.subTest(kind=kind, case=case):
                    malformed = copy.deepcopy(manifest)
                    if case == 'unknown-field':
                        malformed['spec']['unexpectedField'] = True
                    elif case == 'wrong-type':
                        malformed['spec'][field] = invalid
                    else:
                        malformed['apiVersion'] = malformed['apiVersion'].split('/')[0] + '/v999'
                    result = self.validate(malformed)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('could not find schema' if case == 'missing-schema'
                                  else 'is invalid', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
