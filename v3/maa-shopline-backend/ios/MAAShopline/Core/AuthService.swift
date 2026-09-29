import AuthenticationServices
import Foundation

enum AuthError: Error, Equatable { case invalidHandle, cancelled, noSession, failed }

/// SHOPLINE install/sign-in through ASWebAuthenticationSession. The backend redirects to
/// maashopline://auth#session=<token>; the token is read from the fragment only.
@MainActor
final class AuthService: NSObject, ASWebAuthenticationPresentationContextProviding {
    private let config: AppConfig
    private var current: ASWebAuthenticationSession?

    init(config: AppConfig) { self.config = config }

    /// Same rule the backend enforces (app/shopline/oauth.py HANDLE_RE): lowercase store handle only.
    nonisolated static func isValidHandle(_ h: String) -> Bool {
        h.range(of: "^[a-z0-9][a-z0-9-]{0,62}$", options: .regularExpression) != nil
    }

    nonisolated static func startURL(base: URL, handle: String) -> URL {
        var c = URLComponents(url: base.appending(path: "/auth/shopline/start"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "handle", value: handle), URLQueryItem(name: "client", value: "ios")]
        return c.url!
    }

    /// Extracts the session from maashopline://auth#session=... ; rejects anything else.
    nonisolated static func session(from callback: URL) -> String? {
        guard callback.scheme == AppConfig.callbackScheme, callback.host == "auth",
              let fragment = callback.fragment else { return nil }
        let items = URLComponents(string: "x:?" + fragment)?.queryItems ?? []
        guard let token = items.first(where: { $0.name == "session" })?.value, !token.isEmpty else { return nil }
        return token
    }

    func signIn(handle raw: String) async throws -> String {
        let handle = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard Self.isValidHandle(handle) else { throw AuthError.invalidHandle }
        let url = Self.startURL(base: config.apiBaseURL, handle: handle)
        return try await withCheckedThrowingContinuation { cont in
            let s = ASWebAuthenticationSession(url: url, callbackURLScheme: AppConfig.callbackScheme) { callback, error in
                if let e = error as? ASWebAuthenticationSessionError, e.code == .canceledLogin {
                    cont.resume(throwing: AuthError.cancelled); return
                }
                guard error == nil, let callback, let token = Self.session(from: callback) else {
                    cont.resume(throwing: error == nil ? AuthError.noSession : AuthError.failed); return
                }
                cont.resume(returning: token)
            }
            s.presentationContextProvider = self
            s.prefersEphemeralWebBrowserSession = true      // no shared cookies with Safari
            current = s
            if !s.start() { cont.resume(throwing: AuthError.failed) }
        }
    }

    nonisolated func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first ?? ASPresentationAnchor()
        }
    }
}
