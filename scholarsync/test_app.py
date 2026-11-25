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
    def test_conversation_history_and_direct_answer(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module,'DB',Path(tmp)/'runs.sqlite3'), patch.dict(os.environ,{'AI_API_KEY':'test','AI_MODEL':'test'}), patch.object(module,'generate',AsyncMock(side_effect=['A variable stores a value.','For example, int x = 5;'])) as model, patch.object(module.httpx,'AsyncClient',return_value=AsyncMock()):
            with TestClient(module.app) as client:
                first=client.post('/api/conversations/message',json={'message':'What is a Java variable?'}).json()
                cid=first['conversation']
                second=client.post('/api/conversations/message',json={'message':'Give an example','conversation':cid})
                self.assertEqual(second.status_code,200)
                self.assertIn('What is a Java variable?',model.await_args_list[-1].args[2])
                self.assertEqual(len(client.get('/api/conversations/'+cid).json()),4)
                self.assertEqual(len(client.get('/api/conversations').json()),1)
                events=client.get('/api/mission/events').json()['events']
                self.assertEqual(len([e for e in events if e['node']=='direct_answer' and e['status']=='complete']),2)
                self.assertNotIn('Java variable',str(events))
                catalog=client.get('/api/mission/catalog').json()
                self.assertEqual(sum(len(r['agents']) for r in catalog['routes']),93)
                self.assertEqual(len(catalog['routes']),33)
                self.assertEqual(client.get('/mission.js').status_code,200)
                self.assertEqual(client.get('/studio.js').status_code,200)
                self.assertEqual(client.get('/studio.css').status_code,200)
                self.assertIn('cinema-stage',client.get('/').text)
                self.assertEqual(client.get('/studio',follow_redirects=False).status_code,307)
                self.assertIn('Live network',client.get('/').text)
                self.assertEqual(client.get('/cinema/network.js').status_code,200)
                trace=client.get('/api/mission/events/'+first['trace_id']).json()['events']
                self.assertEqual([e['status'] for e in trace],['running','complete'])
                self.assertEqual(client.get('/cinema/app.js').status_code,200)
                clip=client.get('/cinema/assets/aria/intro.mp4',headers={'Range':'bytes=0-1023'})
                self.assertEqual(clip.status_code,206)
                self.assertEqual(len(clip.content),1024)
                self.assertEqual(client.post('/api/conversations/message',json={'message':'  '}).status_code,422)

    def test_document_extraction(self):
        import io,zipfile
        with tempfile.TemporaryDirectory() as tmp, patch.object(module,'DB',Path(tmp)/'runs.sqlite3'):
            with TestClient(module.app) as client:
                r=client.post('/api/document/extract?filename=notes.txt',content=b'Java arrays')
                self.assertEqual(r.json()['text'],'Java arrays')
                buf=io.BytesIO()
                with zipfile.ZipFile(buf,'w') as z:
                    z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:document>')
                self.assertEqual(client.post('/api/document/extract?filename=notes.docx',content=buf.getvalue()).json()['text'],'Hello')
                self.assertEqual(client.post('/api/document/extract?filename=bad.exe',content=b'bad').status_code,422)

    def test_reference_search(self):
        import httpx
        fixture=httpx.Response(200,json={'query':{'search':[{'title':'Java','pageid':123}]}},request=httpx.Request('GET','https://en.wikipedia.org/w/api.php'))
        mock=AsyncMock();mock.__aenter__.return_value.get.return_value=fixture
        with tempfile.TemporaryDirectory() as tmp, patch.object(module,'DB',Path(tmp)/'runs.sqlite3'), patch.object(module.httpx,'AsyncClient',return_value=mock):
            with TestClient(module.app) as client:
                d=client.get('/api/reference-search?q=Java').json()
                self.assertEqual(d['results'][0]['url'],'https://en.wikipedia.org/?curid=123')
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
