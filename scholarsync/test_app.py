import asyncio
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from scholarsync import app as module


class WorkflowTest(unittest.TestCase):
    def test_specialist_chat_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'DB', Path(tmp) / 'runs.sqlite3'), patch.dict(os.environ, {'AI_API_KEY':'test-secret','AI_MODEL':'gpt-4.1-mini','AI_BASE_URL':'https://api.openai.com/v1','SCHOLARSYNC_USERNAME':'owner','SCHOLARSYNC_PASSWORD':'test-password'}), patch.object(module, 'crew_answer', AsyncMock(return_value={'answer':'Test answer','mode':'specialist'})):
            with TestClient(module.app) as client:
                auth = ('owner','test-password')
                self.assertEqual(client.post('/api/chat', json={'message':'Explain Java'}).status_code, 401)
                status = client.get('/api/settings', auth=auth)
                self.assertTrue(status.json()['specialists_configured'])
                self.assertNotIn('test-secret', status.text)
                self.assertEqual(client.post('/api/chat', json={'message':'Explain Java'}, auth=auth, headers={'Origin':'https://example.invalid'}).status_code, 403)
                self.assertEqual(client.post('/api/chat', json={'message':'Explain Java'}, auth=auth).json()['answer'], 'Test answer')

    def test_render_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'DB', Path(tmp) / 'runs.sqlite3'), patch.dict(os.environ, {'RENDER':'true','SCHOLARSYNC_USERNAME':'','SCHOLARSYNC_PASSWORD':''}):
            with TestClient(module.app) as client:
                self.assertEqual(client.get('/api/health').status_code, 200)
                self.assertEqual(client.get('/').status_code, 503)

    def test_workspace_auth(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'DB', Path(tmp) / 'runs.sqlite3'), patch.dict(os.environ, {'SCHOLARSYNC_USERNAME':'owner','SCHOLARSYNC_PASSWORD':'test-password'}):
            with TestClient(module.app) as client:
                self.assertEqual(client.get('/api/health').status_code, 200)
                self.assertEqual(client.get('/api/runs').status_code, 401)
                self.assertEqual(client.get('/api/runs', auth=('owner','test-password')).status_code, 200)

    def test_workflow(self):
        async def fake_invoke(client, role, prompt):
            await asyncio.sleep(.01)
            return f'Test output: {role}'

        @asynccontextmanager
        async def fake_client(**kwargs):
            yield None

        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'DB', Path(tmp) / 'runs.sqlite3'), patch.dict(os.environ, {'AI_API_KEY':'test','AI_MODEL':'test'}), patch.object(module, 'invoke', fake_invoke), patch.object(module.httpx, 'AsyncClient', fake_client):
            with TestClient(module.app) as client:
                self.assertEqual(client.get('/').status_code, 200)
                self.assertTrue(client.get('/api/health').json()['ai_configured'])
                response = client.post('/api/runs', json={'topic':'Compare learning methods'})
                self.assertEqual(response.status_code, 202)
                run_id = response.json()['id']
                with client.stream('GET', f'/api/runs/{run_id}/events') as events:
                    self.assertEqual(events.status_code, 200)
                    list(events.iter_lines())
                run = client.get(f'/api/runs/{run_id}').json()
                self.assertEqual(run['status'], 'complete')
                self.assertEqual(run['report'], 'Test output: report')
                self.assertTrue(all(x['status']=='complete' for x in run['agents'].values()))
                self.assertEqual(len(client.get('/api/runs').json()), 1)


if __name__ == '__main__':
    unittest.main()
