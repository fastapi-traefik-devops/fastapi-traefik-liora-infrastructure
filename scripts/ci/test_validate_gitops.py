from pathlib import Path
import tempfile
import unittest
import yaml
from validate_gitops import validate


class ManifestTests(unittest.TestCase):
    def test_rejects_placeholders_and_mixed_source_pair(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'render.yaml'
            docs = [{'kind': 'Deployment', 'metadata': {'name': n, 'namespace': 'app-prod'}, 'spec': {'template': {'spec': {'containers': [{'name': n, 'image': f'ghcr.io/fastapi-traefik-devops/fastapi-{n}:sha-' + 'a' * 40 + '@sha256:' + 'b' * 64}]}}}} for n in ('backend', 'frontend')]
            def write(): path.write_text(yaml.safe_dump_all(docs))
            write()
            self.assertEqual(validate(path, 'prod'), 2)
            for image in ('backend:latest', 'ghcr.io/fastapi-traefik-devops/fastapi-backend:sha-' + '0' * 40 + '@sha256:' + 'b' * 64, 'ghcr.io/fastapi-traefik-devops/fastapi-backend:sha-' + 'c' * 40 + '@sha256:' + 'b' * 64):
                docs[0]['spec']['template']['spec']['containers'][0]['image'] = image
                write()
                with self.assertRaises(ValueError): validate(path, 'prod')
