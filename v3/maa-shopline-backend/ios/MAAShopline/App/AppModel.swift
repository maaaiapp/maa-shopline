import Foundation
import Observation

/// Screen state used by every feature: mirrors the backend's never-error ladder.
enum Loadable<T: Equatable>: Equatable {
    case idle, loading, loaded(T), empty(String), failed(String)
}

@MainActor @Observable
final class AppModel {
    enum Phase: Equatable { case launching, signedOut, signedIn, misconfigured(String) }

    private(set) var phase: Phase = .launching
    private(set) var connection: Connection?
    let api: APIClient?
    let config: AppConfig?
    private let tokens: TokenStore

    init(tokens: TokenStore = KeychainTokenStore(), session: URLSession = .shared,
         info: [String: Any] = Bundle.main.infoDictionary ?? [:], requireHTTPS: Bool = !AppConfig.isDebug) {
        self.tokens = tokens
        do {
            let cfg = try AppConfig.load(from: info, requireHTTPS: requireHTTPS)
            config = cfg
            api = APIClient(baseURL: cfg.apiBaseURL, tokens: tokens, session: session)
        } catch {
            config = nil; api = nil
            phase = .misconfigured("This build is not configured for a server.")
        }
    }

    func start() async {
        guard api != nil else { return }
        phase = tokens.read() == nil ? .signedOut : .signedIn
        if phase == .signedIn { await refreshConnection() }
    }

    func completeSignIn(token: String) async {
        try? tokens.write(token)
        phase = .signedIn
        await refreshConnection()
    }

    func refreshConnection() async {
        guard let api else { return }
        do {
            connection = try await api.connection()
            if let fresh = try? await api.refreshSession() { try? tokens.write(fresh.session) }   // slide the 12 h window
        } catch APIError.unauthenticated {
            signOut()
        } catch {
            // Keep the last known connection; screens show their own offline state.
        }
    }

    /// Logout: removes the session from this device and all cached merchant data from memory.
    func signOut() {
        tokens.delete()
        connection = nil
        phase = .signedOut
    }

    func deleteAccount() async -> Bool {
        guard let api else { return false }
        do {
            _ = try await api.deleteAccount()
            signOut()
            return true
        } catch APIError.unauthenticated {
            signOut(); return true            // already gone server-side
        } catch {
            return false
        }
    }
}
