import os
import unittest
from unittest.mock import patch, AsyncMock
import httpx
from .provider import generate, ProviderError
from .specialists import execute_specialist, category_from_output, METHODS


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_quota_error_redacted(self):
        with patch.dict(os.environ, {"AI_API_KEY":"fixture","AI_MODEL":"fixture","GROQ_API_KEY":"","GROQ_MODEL":""}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(429,json={"error":{"code":"insufficient_quota","message":"private"}}))) as client:
                with self.assertRaises(ProviderError) as error:
                    await generate(client,"test","test")
                self.assertEqual(error.exception.code,"quota")
                self.assertNotIn("private",str(error.exception))

    async def test_fallback(self):
        calls=[]
        def respond(request):
            calls.append(request.url.host)
            if len(calls)==1:
                return httpx.Response(429,json={"error":{"code":"insufficient_quota"}})
            return httpx.Response(200,json={"choices":[{"message":{"content":"test answer"}}]})
        with patch.dict(os.environ, {"AI_API_KEY":"fixture","AI_MODEL":"fixture","AI_BASE_URL":"https://api.openai.com/v1","GROQ_API_KEY":"fixture2","GROQ_MODEL":"fixture2"}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                self.assertEqual(await generate(client,"test","test"),"test answer")
        self.assertEqual(calls,["api.openai.com","api.groq.com"])

    async def test_retry_after_and_reasoning_budget(self):
        import json
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            if len(calls) == 1:
                return httpx.Response(429, headers={"retry-after":"2"}, json={"error":{"code":"rate_limit_exceeded"}})
            return httpx.Response(200,json={"choices":[{"message":{"content":"OK"}}]})
        with patch.dict(os.environ, {"AI_API_KEY":"","AI_MODEL":"","GROQ_API_KEY":"fixture","GROQ_MODEL":"openai/gpt-oss-20b"}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                self.assertEqual(await generate(client,"test","test",max_tokens=32),"OK")
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]["reasoning_effort"],"low")
        self.assertGreaterEqual(calls[0]["max_tokens"],256)

    async def test_long_retry_window_is_not_ignored(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(429,headers={"retry-after":"120"},json={"error":{"code":"rate_limit_exceeded"}})
        with patch.dict(os.environ, {"AI_API_KEY":"","AI_MODEL":"","GROQ_API_KEY":"fixture","GROQ_MODEL":"fixture"}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                with self.assertRaises(ProviderError) as error:
                    await generate(client,"test","test")
        self.assertEqual(error.exception.code,"rate_limit")
        self.assertEqual(len(calls),1)

    async def test_specialist_math_route(self):
        planner="LANGUAGE: English\nVERDICT: PASS\nCATEGORY: math\nCLEAN REQUEST: Fractions\nBLOCK MESSAGE: none"
        with patch("scholarsync.specialists.generate", AsyncMock(side_effect=[planner,"solution","reviewed answer"])) as model:
            result=await execute_specialist(None,"Explain fractions")
            self.assertEqual(result["route"],"math")
            self.assertEqual(result["answer"],"reviewed answer")
            self.assertEqual(model.await_count,3)

    def test_routes_and_block(self):
        for category in METHODS["route_message"]["emit"]:
            label="quick" if category=="quick_answer" else category
            verdict="BLOCK" if category=="blocked" else "PASS"
            self.assertEqual(category_from_output(f"VERDICT: {verdict}\nCATEGORY: {label}"),category)
        self.assertEqual(category_from_output("unparseable"),"blocked")
