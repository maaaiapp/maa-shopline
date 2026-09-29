import Foundation

enum APIError: Error, Equatable {
    case unauthenticated          // 401: session missing, expired or revoked (uninstall / deletion)
    case notFound
    case server                   // 5xx: backend is designed never to show provider errors
    case network                  // offline, timeout, DNS
    case invalidResponse
    case http(Int)
}

/// Thin async client for the MAA × SHOPLINE API. The token is read from the TokenStore on
/// every call and never logged. A 401 clears the stored session so the app returns to Connect.
struct APIClient: Sendable {
    let baseURL: URL
    let tokens: TokenStore
    let session: URLSession

    init(baseURL: URL, tokens: TokenStore, session: URLSession = .shared) {
        self.baseURL = baseURL; self.tokens = tokens; self.session = session
    }

    func connection() async throws -> Connection { try await send("GET", "/api/connection") }
    func healthCheck() async throws -> HealthCheckResponse { try await send("GET", "/api/health-check") }
    func ask(_ question: String, arabic: Bool) async throws -> AdvisorResponse {
        try await send("POST", "/api/advisor", body: ["question": question, "lang": arabic ? "ar" : "en"])
    }
    func job(_ id: String) async throws -> JobStatus { try await send("GET", "/api/jobs/\(id)") }
    func refreshSession() async throws -> SessionResponse { try await send("POST", "/api/session/refresh") }
    func deleteAccount() async throws -> DeleteResponse { try await send("POST", "/api/account/delete") }

    func send<T: Decodable>(_ method: String, _ path: String, body: [String: String]? = nil) async throws -> T {
        var req = URLRequest(url: baseURL.appending(path: path))
        req.httpMethod = method
        req.timeoutInterval = 30
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        if let t = tokens.read() { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONEncoder().encode(body)
        }
        let result: (Data, URLResponse)
        do { result = try await session.data(for: req) } catch { throw APIError.network }
        let (data, resp) = result
        guard let http = resp as? HTTPURLResponse else { throw APIError.invalidResponse }
        switch http.statusCode {
        case 200..<300:
            do { return try JSONDecoder().decode(T.self, from: data) } catch { throw APIError.invalidResponse }
        case 401: tokens.delete(); throw APIError.unauthenticated
        case 404: throw APIError.notFound
        case 500...: throw APIError.server
        default: throw APIError.http(http.statusCode)
        }
    }
}
