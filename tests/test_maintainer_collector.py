"""Offline behavioral fixtures, not claims of live collector support."""
import hashlib
import errno
import json
import socket
import sys
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maintenance import collector

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
BOOTSTRAP = "https://www.anthropic.com/engineering/multi-agent-research-system"
CANONICAL = "https://www.anthropic.com/research/multi-agent-research-system"
PAPER = "2611.00001v2"


def engineering(body="A bounded experimental system with measured limitations.", published="2025-06-13T00:00:00Z", modified="2026-10-09T06:14:11Z"):
    return f'''<!DOCTYPE html><html><head>
    <meta property="og:title" content="Fixture engineering study">
    <meta property="article:published_time" content="{published}">
    <meta property="article:modified_time" content="{modified}">
    <script type="application/ld+json">{{"@type":"Article","author":{{"name":"Anthropic"}}}}</script>
    </head><body><nav>UNRELATED NAVIGATION</nav><main><article>
    <header><a href="/engineering">Engineering</a></header>
    <h1>Fixture engineering study</h1><div data-article-body="true"><h2>Evaluation</h2>
    <p>{body}</p><script>INJECTED SCRIPT</script><style>HIDDEN STYLE</style>
    <p>Written by Alice Example and Bob Example.</p></div></article></main>
    <footer>UNRELATED FOOTER</footer></body></html>'''.encode()


def entry(identifier=PAPER, updated="2026-11-05T10:00:00Z", published="2026-11-01T10:00:00Z"):
    return f'''<entry><id>http://arxiv.org/abs/{identifier}</id><title>Fixture agent experiment</title>
    <published>{published}</published><updated>{updated}</updated><author><name>Alice Example</name></author>
    <summary>Abstract claims only, not complete methods.</summary></entry>'''


def atom(entries=""):
    return ('<feed xmlns="http://www.w3.org/2005/Atom">' + entries + '</feed>').encode()


def journal_item():
    return {"DOI": "10.1038/s42256-026-00001-1", "type": "journal-article", "ISSN": ["2522-5839"],
            "title": ["Fixture journal experiment"], "author": [{"given": "Alice", "family": "Example"}],
            "published": {"date-parts": [[2026, 10, 1]]},
            "deposited": {"date-time": "2026-10-02T10:00:00Z"},
            "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/", "content-version": "vor"}]}


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.routes = {}
        self.clock = 100.0
        self.addCleanup(patch.stopall)
        self.real_request_once = collector._request_once
        patch.object(collector, "_request_once", side_effect=self.request).start()
        patch.object(collector.time, "monotonic", side_effect=lambda: self.clock).start()
        patch.object(collector.time, "sleep", side_effect=self.sleep).start()
        patch.object(collector, "_arxiv_last_finished", None).start()

    def sleep(self, seconds):
        self.clock += seconds

    def request(self, url, *, deadline):
        self.requests.append((url, self.clock))
        for prefix, response in self.routes.items():
            if url.startswith(prefix):
                if isinstance(response, Exception):
                    raise response
                return response
        raise collector.CollectionError("fixture endpoint unavailable")

    def defaults(self, *, arxiv=b"", items=None, index=b"<main></main>"):
        self.routes["https://export.arxiv.org/api/query"] = (200, {"content-type": "application/atom+xml"}, arxiv or atom())
        self.routes["https://api.crossref.org/journals/"] = (200, {"content-type": "application/json"}, json.dumps({"status": "ok", "message": {"items": items or []}}).encode())
        self.routes["https://www.anthropic.com/engineering"] = (200, {"content-type": "text/html"}, index)

    def bootstrap(self, html=None):
        self.routes[BOOTSTRAP] = (301, {"location": CANONICAL}, b"")
        self.routes[CANONICAL] = (200, {"content-type": "text/html"}, html or engineering())
        return collector.fetch_candidate(BOOTSTRAP, now=NOW)

    def test_bootstrap_is_honestly_dated_engineering_with_private_evidence(self):
        candidate = self.bootstrap()
        self.assertEqual(candidate.url, CANONICAL)
        self.assertEqual(candidate.published, "2025-06-13T00:00:00Z")
        self.assertEqual(candidate.updated, "2026-10-09T06:14:11Z")
        self.assertEqual(candidate.tier, "engineering")
        self.assertEqual(candidate.authors, ("Alice Example", "Bob Example"))
        packet = candidate.documents[0]
        self.assertTrue(packet.complete)
        self.assertIn("measured limitations", packet.text)
        self.assertIn("unknown", packet.text.lower())
        self.assertIn("reference-only", packet.text)
        self.assertEqual(packet.sha256, hashlib.sha256(packet.text.encode()).hexdigest())
        for excluded in ("UNRELATED NAVIGATION", "UNRELATED FOOTER", "INJECTED SCRIPT", "HIDDEN STYLE"):
            self.assertNotIn(excluded, packet.text)

    def test_content_revision_changes_key_but_not_publication(self):
        first = self.bootstrap()
        second = self.bootstrap(engineering(body="Revised bounded experiment."))
        self.assertNotEqual(first.key, second.key)
        self.assertEqual(first.published, second.published)
    def test_biographical_and_acknowledgment_prose_never_becomes_authors(self):
        examples = (
            ("Written by Prithvi Rajasekaran, a member of our Labs team.", ("Prithvi Rajasekaran",)),
            ("Written by Tristan Hume, a lead on Anthropic's performance optimization team. Tristan designed—and redesigned—the take-home test.", ("Tristan Hume",)),
            ("Written by Nick G. and the source control team: S.G., R.K., Dan C., Garrett H., Ben L., Colin M., Joe P. We’re grateful to Vilas J. and Sergiu D. for supporting the team.", ("Nick G.", "source control team", "S.G.", "R.K.", "Dan C.", "Garrett H.", "Ben L.", "Colin M.", "Joe P.")),
        )
        for credit, authors in examples:
            with self.subTest(credit=credit):
                html = engineering().replace(b"Written by Alice Example and Bob Example.", credit.encode())
                candidate = self.bootstrap(html)
                self.assertEqual(candidate.authors, authors)

    def test_structured_person_authorship_precedes_unstructured_byline(self):
        html = engineering().replace(b'{"name":"Anthropic"}', b'{"@type":"Person","name":"Person From Structured Metadata"}')
        candidate = self.bootstrap(html)
        self.assertEqual(candidate.authors, ("Person From Structured Metadata",))

    def test_unparseable_byline_uses_only_explicit_organization_credit(self):
        html = engineering().replace(b"Written by Alice Example and Bob Example.", b"Written by someone whose identity is not supplied.")
        candidate = self.bootstrap(html)
        self.assertEqual(candidate.authors, ("Anthropic",))


    def test_unsafe_urls_never_reach_transport(self):
        urls = ["http://www.anthropic.com/engineering/test", "file:///etc/passwd", "https://127.0.0.1/", "https://[::1]/",
                "https://www.anthropic.com.evil.invalid/engineering/test", "https://u:p@www.anthropic.com/engineering/test",
                "https://www.anthropic.com:444/engineering/test", "https://www.anthropic.com./engineering/test",
                "https://www.anthropic.com/engineering/test#fragment", "https://www.anthropic.com/engineering/../secret",
                "https://www.anthropic.com/engineering/%2e%2e/secret", "https://www.anthropic.com\\@evil.invalid/engineering/test"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(collector.CollectionError):
                collector.fetch_candidate(url, now=NOW)
        self.assertEqual(self.requests, [])

    def test_redirect_targets_are_validated_before_fetch(self):
        for target in ("http://www.anthropic.com/engineering/x", "https://localhost/", "https://www.nature.com/articles/x", "https://www.anthropic.com:8443/engineering/x"):
            self.routes[BOOTSTRAP] = (302, {"location": target}, b"")
            with self.subTest(target=target), self.assertRaises(collector.CollectionError):
                collector.fetch_candidate(BOOTSTRAP, now=NOW)
        self.assertEqual(len(self.requests), 4)

    def test_redirect_loop_is_bounded(self):
        self.routes[BOOTSTRAP] = (302, {"location": BOOTSTRAP}, b"")
        with self.assertRaises(collector.CollectionError):
            collector.fetch_candidate(BOOTSTRAP, now=NOW)
        self.assertLessEqual(len(self.requests), 5)

    def test_dns_private_or_mixed_resolution_is_rejected(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch.object(socket, "getaddrinfo", return_value=answers), self.assertRaises(collector.CollectionError):
            collector._public_addresses("www.anthropic.com")
        answers.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)))
        with patch.object(socket, "getaddrinfo", return_value=answers), self.assertRaises(collector.CollectionError):
            collector._public_addresses("www.anthropic.com")
    def test_connection_tries_remaining_validated_addresses_with_tls_hostname(self):
        from unittest.mock import MagicMock
        connection = collector._PinnedHTTPS("export.arxiv.org", timeout=15)
        raw = MagicMock()
        tls = MagicMock()
        context = MagicMock()
        context.wrap_socket.return_value = tls
        connection._context = context
        with patch.object(collector, "_public_addresses", return_value=("151.101.131.42", "151.101.67.42")), patch.object(socket, "create_connection", side_effect=[OSError(errno.ENETUNREACH, "no route"), raw]) as connect:
            connection.connect()
        self.assertEqual([call.args[0] for call in connect.call_args_list], [("151.101.131.42", 443), ("151.101.67.42", 443)])
        context.wrap_socket.assert_called_once_with(raw, server_hostname="export.arxiv.org")
        self.assertIs(connection.sock, tls)

    def test_all_address_failures_keep_nonsecret_errno_diagnostics(self):
        connection = collector._PinnedHTTPS("export.arxiv.org", timeout=15)
        with patch.object(collector, "_public_addresses", return_value=("151.101.131.42", "151.101.67.42")), patch.object(socket, "create_connection", side_effect=[OSError(errno.ENETUNREACH, "PRIVATE_ERROR_DETAIL"), OSError(errno.ECONNREFUSED, "PRIVATE_ERROR_DETAIL")]):
            with self.assertRaises(collector.CollectionError) as caught:
                connection.connect()
        self.assertIn("ENETUNREACH", str(caught.exception))
        self.assertIn("ECONNREFUSED", str(caught.exception))
        self.assertNotIn("PRIVATE_ERROR_DETAIL", str(caught.exception))

    def test_tls_certificate_error_does_not_try_another_identity(self):
        import ssl
        from unittest.mock import MagicMock
        connection = collector._PinnedHTTPS("export.arxiv.org", timeout=15)
        raw = MagicMock()
        connection._context = MagicMock()
        connection._context.wrap_socket.side_effect = ssl.SSLCertVerificationError("private detail")
        with patch.object(collector, "_public_addresses", return_value=("151.101.131.42", "151.101.67.42")), patch.object(socket, "create_connection", return_value=raw) as connect:
            with self.assertRaises(ssl.SSLCertVerificationError):
                connection.connect()
        self.assertEqual(connect.call_count, 1)
        raw.close.assert_called_once()


    def test_source_failures_are_not_empty_success(self):
        self.defaults(arxiv=b"<feed>")
        self.routes["https://api.crossref.org/journals/"] = OSError("unavailable")
        self.routes["https://www.anthropic.com/engineering"] = (503, {}, b"unavailable")
        result = collector.collect(NOW)
        self.assertEqual(result.candidates, ())
        self.assertEqual(len(result.errors), 3)

    def test_unsafe_xml_dtd_entities_and_wide_encoding_are_rejected(self):
        for content in (b'<!DOCTYPE feed [<!ENTITY a "danger">]><feed>&a;</feed>', b'<!ENTITY a SYSTEM "file:///etc/passwd"><feed/>', '<!DOCTYPE feed><feed/>'.encode("utf-16")):
            self.defaults(arxiv=content)
            result = collector.collect(NOW)
            self.assertEqual(result.candidates, ())
            self.assertTrue(result.errors)

    def test_wrong_xml_root_and_arxiv_error_entry_are_failures(self):
        for content in (b"<html/>", atom('<entry><id>http://arxiv.org/api/errors#bad</id><title>Error</title></entry>')):
            self.defaults(arxiv=content)
            self.assertTrue(collector.collect(NOW).errors)

    def test_versions_deduplicate_by_version_and_preserve_time(self):
        self.defaults(arxiv=atom(entry() + entry() + entry("2611.00001v1")))
        self.routes["https://arxiv.org/html/"] = (200, {"content-type": "text/html"}, b'<html><article class="ltx_document"><h2>Methods</h2><p>Actual methods and limitations.</p></article></html>')
        result = collector.collect(NOW, seen={"arxiv:2611.00001v1"})
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].key, "arxiv:2611.00001v2")
        self.assertEqual(result.candidates[0].tier, "preprint")
        self.assertEqual(result.candidates[0].updated, "2026-11-05T10:00:00Z")
        self.assertTrue(result.candidates[0].documents[0].complete)
        self.assertEqual(sum(url.startswith("https://arxiv.org/html/") for url, _ in self.requests), 1)

    def test_arxiv_requests_share_one_lock_and_three_second_spacing(self):
        self.defaults(arxiv=atom(entry()))
        self.routes["https://arxiv.org/html/"] = (404, {}, b"")
        collector.collect(NOW)
        collector.collect(NOW)
        starts = [at for url, at in self.requests if "arxiv.org/" in url]
        self.assertTrue(all(b - a >= 3 for a, b in zip(starts, starts[1:])))

    def test_concurrent_arxiv_fetches_never_overlap(self):
        first_entered = threading.Event()
        release_first = threading.Event()
        second_started = threading.Event()
        second_entered = threading.Event()
        calls = []
        failures = []

        def transport(url, *, deadline):
            calls.append(url)
            if len(calls) == 1:
                first_entered.set()
                release_first.wait(2)
            else:
                second_entered.set()
            return 200, {"content-type": "application/atom+xml"}, atom()

        def fetch(second=False):
            try:
                if second:
                    second_started.set()
                collector._fetch("https://export.arxiv.org/api/query", kind="xml")
            except Exception as exc:
                failures.append(exc)

        with patch.object(collector, "_request_once", side_effect=transport):
            first = threading.Thread(target=fetch)
            second = threading.Thread(target=fetch, args=(True,))
            first.start()
            try:
                self.assertTrue(first_entered.wait(1))
                second.start()
                self.assertTrue(second_started.wait(1))
                self.assertFalse(second_entered.wait(0.02))
            finally:
                release_first.set()
                first.join(2)
                if second.ident is not None:
                    second.join(2)
        self.assertEqual(failures, [])
        self.assertEqual(len(calls), 2)

    def test_abstract_only_unavailable_html_is_incomplete_and_visible(self):
        self.defaults(arxiv=atom(entry()))
        self.routes["https://arxiv.org/html/"] = (404, {}, b"")
        result = collector.collect(NOW)
        self.assertEqual(len(result.candidates), 1)
        self.assertFalse(result.candidates[0].documents[0].complete)
        self.assertIn("abstract-only", result.candidates[0].documents[0].text)
        self.assertTrue(result.errors)

    def test_partial_entry_does_not_hide_valid_sibling(self):
        self.defaults(arxiv=atom('<entry><title>Missing identifier</title></entry>' + entry()))
        self.routes["https://arxiv.org/html/"] = (404, {}, b"")
        result = collector.collect(NOW)
        self.assertEqual(len(result.candidates), 1)
        self.assertTrue(result.errors)

    def test_future_missing_and_reversed_dates_do_not_become_now(self):
        for published, updated in (("2027-01-01T00:00:00Z", "2027-01-01T00:00:00Z"), ("", "2026-11-01T00:00:00Z"), ("2026-11-02T00:00:00Z", "2026-11-01T00:00:00Z")):
            self.defaults(arxiv=atom(entry(published=published, updated=updated)))
            result = collector.collect(NOW)
            self.assertEqual(result.candidates, ())
            self.assertTrue(result.errors)
        with self.assertRaises(ValueError):
            collector.collect(datetime(2026, 11, 6))

    def test_bounded_text_and_payload_are_never_complete(self):
        with patch.object(collector, "MAX_TEXT_CHARS", 120):
            candidate = self.bootstrap(engineering(body="Long source text. " * 40))
        self.assertFalse(candidate.documents[0].complete)
        self.assertIn("truncated", candidate.documents[0].text)
        self.routes[BOOTSTRAP] = (200, {"content-type": "text/html"}, b"x" * (collector.MAX_RESPONSE_BYTES + 1))
        with self.assertRaises(collector.CollectionError):
            collector.fetch_candidate(BOOTSTRAP, now=NOW)

    def test_unclosed_article_does_not_become_complete(self):
        candidate = self.bootstrap(engineering().replace(b"</article>", b""))
        self.assertFalse(candidate.documents[0].complete)

    def test_unrelated_official_research_is_not_labeled_engineering(self):
        html = engineering().replace(b'<a href="/engineering">Engineering</a>', b'<a href="/science">Science</a>')
        self.routes[CANONICAL] = (200, {"content-type": "text/html"}, html)
        with self.assertRaises(collector.CollectionError):
            collector.fetch_candidate(CANONICAL, now=NOW)

    def test_engineering_requires_identity_and_real_body_not_metadata_only(self):
        for html in (b"<html><head><title>Error</title></head><body>Unavailable</body></html>", engineering().replace(b"article:published_time", b"missing-date"), engineering().replace(b"<h2>Evaluation</h2>", b"")):
            self.routes[BOOTSTRAP] = (200, {"content-type": "text/html"}, html)
            with self.assertRaises(collector.CollectionError):
                collector.fetch_candidate(BOOTSTRAP, now=NOW)

    def test_engineering_discovery_uses_official_index_and_deduplicates(self):
        self.defaults(index=f'<main><a href="{CANONICAL}">Study</a><a href="{CANONICAL}">Again</a><a href="https://evil.invalid/x">No</a></main>'.encode())
        self.routes[CANONICAL] = (200, {"content-type": "text/html"}, engineering())
        result = collector.collect(NOW)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].discovery_source, "https://www.anthropic.com/engineering")
        seen = collector.collect(NOW, seen={result.candidates[0].key})
        self.assertEqual(seen.candidates, ())

    def test_incomplete_newer_sources_do_not_starve_complete_evidence(self):
        self.defaults(arxiv=atom(entry()), index=f'<main><a href="{CANONICAL}">Engineering study</a></main>'.encode())
        self.routes["https://arxiv.org/html/"] = (404, {}, b"")
        self.routes[CANONICAL] = (200, {"content-type": "text/html"}, engineering())
        result = collector.collect(NOW, limit=1)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].tier, "engineering")
        self.assertTrue(result.candidates[0].documents[0].complete)
        self.assertTrue(result.errors)

    def test_journal_metadata_is_constrained_and_paywall_not_full_methods(self):
        self.defaults(items=[journal_item()])
        self.routes["https://www.nature.com/articles/"] = (200, {"content-type": "text/html"}, b'<article><meta name="citation_article_type" content="Article"><meta name="citation_doi" content="10.1038/s42256-026-00001-1"><h2>Abstract</h2><p>Only a preview.</p></article>')
        result = collector.collect(NOW)
        candidate = result.candidates[0]
        self.assertEqual(candidate.tier, "peer-reviewed")
        self.assertFalse(candidate.documents[0].complete)
        self.assertIn("content-version", candidate.documents[0].text)
        self.assertIn("reference-only", candidate.documents[0].text)
        self.assertTrue(result.errors)

    def test_crossref_listing_alone_cannot_establish_peer_review(self):
        self.defaults(items=[journal_item()])
        self.routes["https://www.nature.com/articles/"] = (200, {"content-type": "text/html"}, b'<article><meta name="citation_article_type" content="Editorial"><h2>Discussion</h2>Not reviewed research.</article>')
        result = collector.collect(NOW)
        self.assertEqual(result.candidates, ())
        self.assertTrue(result.errors)

    def test_crossref_wrong_journal_and_malformed_items_are_visible(self):
        item = journal_item()
        item["ISSN"] = ["0000-0000"]
        self.defaults(items=[item, {"title": ["Partial"]}])
        result = collector.collect(NOW)
        self.assertEqual(result.candidates, ())
        self.assertEqual(len(result.errors), 2)

    def test_journal_full_methods_and_license_revision_are_preserved(self):
        item = journal_item()
        self.defaults(items=[item])
        self.routes["https://www.nature.com/articles/"] = (200, {"content-type": "text/html"}, b'<article><meta name="citation_article_type" content="Article"><meta name="citation_doi" content="10.1038/s42256-026-00001-1"><h2>Methods</h2><p>Measured experiment and its limitations.</p></article>')
        first = collector.collect(NOW).candidates[0]
        self.assertTrue(first.documents[0].complete)
        item["license"][0]["content-version"] = "am"
        self.defaults(items=[item])
        revised = collector.collect(NOW).candidates[0]
        self.assertNotEqual(first.key, revised.key)
        self.assertEqual(first.published, revised.published)
        self.assertIn('"content-version": "am"', revised.documents[0].text)
    def test_official_publisher_cookie_round_trip_preserves_canonical_identity(self):
        from urllib.parse import urlencode
        item = journal_item()
        article = "https://www.nature.com/articles/s42256-026-00001-1"
        authorize = "https://idp.nature.com/authorize?" + urlencode({"response_type": "cookie", "client_id": "grover", "redirect_uri": article})
        transit = "https://idp.nature.com/transit?" + urlencode({"redirect_uri": article, "code": "public-round-trip"})
        returned = article + "?error=cookies_not_supported&code=public-round-trip"
        self.defaults(items=[item])
        self.routes[article] = (303, {"location": authorize}, b"")
        self.routes[authorize] = (302, {"location": transit, "set-cookie": "must-not-be-persisted"}, b"")
        self.routes[transit] = (302, {"location": returned}, b"")
        body = ('<html><head><link rel="canonical" href="' + article + '"><meta name="citation_article_type" content="Article"><meta name="citation_doi" content="' + item["DOI"] + '"></head><body><article><h2>Methods</h2><p>Actual methods and limitations.</p></article></body></html>').encode()
        self.routes = {returned: (200, {"content-type": "text/html"}, body), **self.routes}
        candidate = collector.collect(NOW).candidates[0]
        self.assertEqual(candidate.url, article)
        self.assertEqual(candidate.documents[0].url, article)
        self.assertTrue(candidate.documents[0].complete)
        self.assertNotIn("public-round-trip", candidate.documents[0].text)

    def test_publisher_redirect_exceptions_are_exact_and_not_general_cross_host(self):
        from urllib.parse import urlencode
        article = "https://www.nature.com/articles/s42256-026-00001-1"
        targets = (
            "https://idp.nature.com/authorize?" + urlencode({"response_type": "cookie", "client_id": "grover", "redirect_uri": "https://www.nature.com/articles/s42256-026-99999-1"}),
            "https://idp.nature.com/authorize?" + urlencode({"response_type": "cookie", "client_id": "grover", "redirect_uri": "https://evil.invalid/"}),
            "https://idp.nature.com/admin",
            "https://idp.nature.com.evil.invalid/authorize",
            "https://www.nature.com/articles/s42256-026-99999-1",
        )
        for target in targets:
            self.defaults(items=[journal_item()])
            self.routes[article] = (303, {"location": target}, b"")
            before = len(self.requests)
            result = collector.collect(NOW)
            self.assertEqual(result.candidates, ())
            self.assertTrue(result.errors)
            self.assertNotIn(target, [url for url, _ in self.requests[before:]])

    def test_missing_crossref_authors_use_verified_publisher_authors(self):
        item = journal_item()
        item.pop("author")
        self.defaults(items=[item])
        self.routes["https://www.nature.com/articles/"] = (200, {"content-type": "text/html"}, b'<article><meta name="citation_article_type" content="Article"><meta name="citation_doi" content="10.1038/s42256-026-00001-1"><meta name="citation_author" content="Verified, Alice"><h2>Methods</h2><p>Actual methods.</p></article>')
        candidate = collector.collect(NOW).candidates[0]
        self.assertEqual(candidate.authors, ("Verified, Alice",))
        self.assertTrue(candidate.documents[0].complete)

    def test_publisher_canonical_cannot_change_the_crossref_work(self):
        self.defaults(items=[journal_item()])
        self.routes["https://www.nature.com/articles/"] = (200, {"content-type": "text/html"}, b'<article><link rel="canonical" href="https://www.nature.com/articles/s42256-026-99999-1"><meta name="citation_article_type" content="Article"><meta name="citation_doi" content="10.1038/s42256-026-00001-1"><h2>Methods</h2>Unrelated identity.</article>')
        result = collector.collect(NOW)
        self.assertEqual(result.candidates, ())
        self.assertTrue(result.errors)


    def test_publisher_identity_must_match_requested_journal_work(self):
        self.defaults(items=[journal_item()])
        for doi in ("", '<meta name="citation_doi" content="10.1038/s42256-026-99999-1">'):
            self.routes["https://www.nature.com/articles/"] = (200, {"content-type": "text/html"}, ('<article><meta name="citation_article_type" content="Article">' + doi + '<h2>Methods</h2><p>Unrelated work.</p></article>').encode())
            result = collector.collect(NOW)
            self.assertEqual(result.candidates, ())
            self.assertTrue(result.errors)

    def test_fixed_length_responses_return_complete_bytes_or_report_truncation(self):
        import http.client
        payload = b"complete public metadata"
        for length in (len(payload), len(payload) + 1):
            with self.subTest(advertised_length=length):
                client, peer = socket.socketpair()
                self.addCleanup(client.close)
                self.addCleanup(peer.close)
                peer.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: " + str(length).encode() + b"\r\n\r\n" + payload)
                peer.shutdown(socket.SHUT_WR)
                connection = http.client.HTTPConnection("www.anthropic.com")
                connection.sock = client
                with patch.object(collector, "_PinnedHTTPS", return_value=connection):
                    if length == len(payload):
                        status, _, body = self.real_request_once(BOOTSTRAP, deadline=120)
                        self.assertEqual((status, body), (200, payload))
                    else:
                        with self.assertRaisesRegex(collector.CollectionError, "partial source response"):
                            self.real_request_once(BOOTSTRAP, deadline=120)


    def test_invalid_content_type_compressed_and_partial_http_are_rejected(self):
        for status, headers in ((206, {"content-type": "text/html"}), (200, {"content-type": "application/pdf"}), (200, {"content-type": "text/html", "content-encoding": "gzip"})):
            self.routes[BOOTSTRAP] = (status, headers, engineering())
            with self.assertRaises(collector.CollectionError):
                collector.fetch_candidate(BOOTSTRAP, now=NOW)

    def test_limit_is_bounded_and_no_semantic_routing_fields_are_emitted(self):
        for limit in (-1, 4, True):
            with self.assertRaises(ValueError):
                collector.collect(NOW, limit=limit)
        self.assertEqual(collector.collect(NOW, limit=0).candidates, ())
        self.assertEqual(self.requests, [])
        candidate = self.bootstrap()
        self.assertFalse(hasattr(candidate, "workflow"))
        self.assertFalse(hasattr(candidate, "recommendation"))


if __name__ == "__main__":
    unittest.main()
