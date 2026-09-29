import XCTest
@testable import MAAShopline

/// Intercepts URLSession traffic so API behaviour is tested without a network.
final class StubProtocol: URLProtocol {
    nonisolated(unsafe) static var handler: ((URLRequest) -> (Int, Data))?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let (code, data) = Self.handler!(request)
        let resp = HTTPURLResponse(url: request.url!, statusCode: code, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

final class MAAShoplineTests: XCTestCase {
    private func client(_ tokens: TokenStore) -> APIClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [StubProtocol.self]
        return APIClient(baseURL: URL(string: "https://api.example.test")!, tokens: tokens, session: URLSession(configuration: cfg))
    }

    func testReleaseConfigRequiresHTTPS() {
        XCTAssertThrowsError(try AppConfig.load(from: ["MAAAPIBaseURL": "http://x.test"], requireHTTPS: true))
        XCTAssertThrowsError(try AppConfig.load(from: [:], requireHTTPS: false))
        XCTAssertNoThrow(try AppConfig.load(from: ["MAAAPIBaseURL": "https://x.test"], requireHTTPS: true))
    }

    func testHandleRuleMatchesBackend() {
        XCTAssertTrue(AuthService.isValidHandle("my-store1"))
        for bad in ["", "UPPER", "evil.com/x", "a.b", "shop1.attacker", String(repeating: "x", count: 70)] {
            XCTAssertFalse(AuthService.isValidHandle(bad), bad)
        }
    }

    func testStartURLMarksIOSClient() {
        let u = AuthService.startURL(base: URL(string: "https://api.example.test")!, handle: "shop1")
        XCTAssertEqual(u.absoluteString, "https://api.example.test/auth/shopline/start?handle=shop1&client=ios")
    }

    func testSessionOnlyFromOwnSchemeAndFragment() {
        XCTAssertEqual(AuthService.session(from: URL(string: "maashopline://auth#session=abc.def")!), "abc.def")
        XCTAssertNil(AuthService.session(from: URL(string: "maashopline://auth?session=abc")!))     // query rejected
        XCTAssertNil(AuthService.session(from: URL(string: "evil://auth#session=abc")!))
        XCTAssertNil(AuthService.session(from: URL(string: "maashopline://other#session=abc")!))
        XCTAssertNil(AuthService.session(from: URL(string: "maashopline://auth#session=")!))
    }

    func testBearerSentAnd401ClearsSession() async {
        let tokens = MemoryTokenStore("tok")
        StubProtocol.handler = { req in
            XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer tok")
            return (401, Data(#"{"detail":"session_revoked"}"#.utf8))
        }
        do { _ = try await client(tokens).connection(); XCTFail("expected 401") }
        catch { XCTAssertEqual(error as? APIError, .unauthenticated) }
        XCTAssertNil(tokens.read())
    }

    func testAdvisorQueuedDecodes() async throws {
        StubProtocol.handler = { _ in (200, Data(#"{"state":"queued","answer":null,"generated_at":null,"job_id":"j1","reason":"capacity"}"#.utf8)) }
        let r = try await client(MemoryTokenStore("t")).ask("why?", arabic: false)
        XCTAssertEqual(r.state, "queued"); XCTAssertEqual(r.jobId, "j1")
    }

    func testHealthCheckUnscoredDecodes() async throws {
        let body = #"{"state":"degraded","result":{"overall":null,"binding_constraint":null,"maintenance":false,"coverage":"0 of 5","dimensions":[{"key":"repeat_rate","state":"unscored","score":null,"needs":"orders_read","inputs":null}]}}"#
        StubProtocol.handler = { _ in (200, Data(body.utf8)) }
        let hc = try await client(MemoryTokenStore("t")).healthCheck()
        XCTAssertNil(hc.result.overall); XCTAssertEqual(hc.result.dimensions.first?.state, "unscored")
    }

    func testServerErrorNeverSurfacesBody() async {
        StubProtocol.handler = { _ in (500, Data(#"{"state":"error","reason":"server"}"#.utf8)) }
        do { _ = try await client(MemoryTokenStore("t")).healthCheck(); XCTFail() }
        catch { XCTAssertEqual(error as? APIError, .server) }
    }

    func testJSONValueDisplay() throws {
        let v = try JSONDecoder().decode(JSONValue.self, from: Data(#"{"next_step":"Email lapsed buyers","reach":3}"#.utf8))
        XCTAssertEqual(v.displayText, "Next Step: Email lapsed buyers\nReach: 3")
    }

    @MainActor
    func testLogoutClearsSessionAndData() async {
        let tokens = MemoryTokenStore("tok")
        let m = AppModel(tokens: tokens, info: ["MAAAPIBaseURL": "https://x.test"], requireHTTPS: true)
        m.signOut()
        XCTAssertNil(tokens.read()); XCTAssertNil(m.connection); XCTAssertEqual(m.phase, .signedOut)
    }

    @MainActor
    func testInsecureReleaseBuildIsMisconfiguredNotCrashing() {
        let m = AppModel(tokens: MemoryTokenStore(), info: ["MAAAPIBaseURL": "http://x.test"], requireHTTPS: true)
        if case .misconfigured = m.phase {} else { XCTFail("expected misconfigured") }
    }
}
