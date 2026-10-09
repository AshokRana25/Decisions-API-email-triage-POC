"""Exercise the real installed SDK with an in-memory transport. No network calls."""
import importlib.util
import json
import unittest
from unittest.mock import patch
from triage.contracts import Email
from triage.providers import OpenAIProvider, ProviderError, fixture_payload
from triage.service import run

SDK_AVAILABLE = importlib.util.find_spec("openai") is not None


@unittest.skipUnless(SDK_AVAILABLE, "Install requirements.txt for SDK transport tests")
class SDKTransportTests(unittest.TestCase):
    def provider(self, handler):
        import openai
        import httpx2
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.sdk = openai
        provider.client = openai.OpenAI(api_key="unit-test-placeholder", max_retries=0, timeout=20,
                                        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
        self.addCleanup(provider.close)
        return provider

    def response(self, status=200, payload=None, headers=None):
        import httpx2
        if payload is None:
            payload = fixture_payload(.95, "technical", 1)
            payload["model"] = "gpt-6-luna"
            payload["usage"] = {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                                "output_tokens": 0, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 100}
        return httpx2.Response(status, json=payload, headers=headers)

    def test_sdk_exact_request_and_reply(self):
        seen = []
        def handler(request):
            seen.append(request)
            body = json.loads(request.content)
            self.assertEqual(request.method, "POST")
            self.assertEqual(str(request.url), "https://api.openai.com/v1/decisions")
            self.assertEqual(set(body), {"model", "input", "questions"})
            self.assertEqual(body["model"], "gpt-6-luna")
            self.assertEqual(json.loads(body["input"]), {"subject": "Error", "body": "Please fix the error"})
            self.assertEqual([q["type"] for q in body["questions"]], ["predicate", "choice", "score"])
            return self.response()
        result = run(Email("Error", "Please fix the error"), self.provider(handler), .1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.input_tokens, 100)

    def test_429_retries_once_honoring_retry_after(self):
        seen = []
        def handler(request):
            seen.append(request)
            return self.response(429, {"error": {"message": "rate limit", "type": "rate_limit_error"}}, {"retry-after": "1"}) if len(seen) == 1 else self.response()
        with patch("triage.providers.time.sleep") as sleep:
            result = run(Email("Test", "Body"), self.provider(handler), .1)
        self.assertEqual(result.attempts, 2)
        sleep.assert_called_once_with(1)
        self.assertIsNone(result.estimated_cost_usd)

    def test_retry_budget_stops_at_two(self):
        seen = []
        def handler(request):
            seen.append(request)
            return self.response(500, {"error": {"message": "temporary"}})
        with patch("triage.providers.time.sleep"):
            result = run(Email("Test", "Body"), self.provider(handler))
        self.assertEqual(len(seen), 2)
        self.assertEqual(result.status, "api_status_error")
        self.assertTrue(result.recommendation.abstained)

    def test_long_retry_after_defers_without_retry(self):
        with patch("triage.providers.time.sleep") as sleep:
            result = run(Email("Test", "Body"), self.provider(lambda r: self.response(429, {"error": {}}, {"retry-after": "60"})))
        self.assertEqual(result.attempts, 1)
        sleep.assert_not_called()

    def test_authentication_and_quota_never_retry_or_echo_body(self):
        for status, code in [(401, "invalid_api_key"), (429, "insufficient_quota")]:
            provider = self.provider(lambda r: self.response(status, {"error": {"code": code, "message": "do-not-echo-this-content"}}))
            with patch("triage.providers.time.sleep") as sleep:
                result = run(Email("Test", "Body"), provider)
            sleep.assert_not_called()
            self.assertNotIn("do-not-echo", json.dumps(result.to_dict()))
            self.assertEqual(result.attempts, 1)

    def test_timeout_no_retry(self):
        import httpx2
        def handler(request):
            raise httpx2.ReadTimeout("do-not-echo-sensitive-content", request=request)
        result = run(Email("Test", "Body"), self.provider(handler))
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.status, "connection_or_timeout_error")

    def test_malformed_json_fails_closed(self):
        import httpx2
        result = run(Email("Test", "Body"), self.provider(lambda r: httpx2.Response(200, content=b'{oops', headers={"content-type": "application/json"})))
        self.assertEqual(result.status, "invalid_response")
        self.assertTrue(result.recommendation.abstained)

    def test_malformed_field_does_not_leak_serializer_warnings(self):
        import warnings
        payload = fixture_payload(.95, "technical", 1)
        payload["answers"][0]["probability"] = "synthetic-sensitive-sentinel"
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            result = run(Email("Test", "Body"), self.provider(lambda r: self.response(payload=payload)))
        self.assertEqual(result.status, "invalid_response")
        self.assertFalse(any("synthetic-sensitive-sentinel" in str(w.message) for w in seen))

    def test_non_object_json_fails_closed(self):
        import httpx2
        for payload in [[], "a string", 42, None]:
            with self.subTest(payload=payload):
                result = run(Email("Test", "Body"), self.provider(lambda r: httpx2.Response(200, json=payload)))
                self.assertEqual(result.status, "invalid_response")
                self.assertTrue(result.recommendation.abstained)

    def test_live_constructor_fixed_host_and_no_automatic_retry(self):
        import openai
        with patch.dict("os.environ", {"OPENAI_API_KEY": "unit-test-placeholder"}, clear=True):
            with patch.object(openai, "OpenAI") as client:
                provider = OpenAIProvider(allow_live=True)
                self.addCleanup(provider.close)
                self.assertEqual(client.call_args.kwargs["base_url"], "https://api.openai.com/v1")
                self.assertEqual(client.call_args.kwargs["max_retries"], 0)
                self.assertEqual(client.call_args.kwargs["timeout"], 20)


if __name__ == "__main__":
    unittest.main()
