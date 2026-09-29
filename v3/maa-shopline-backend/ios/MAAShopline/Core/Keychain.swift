import Foundation
import Security

/// Stores the MAA session token. Device-only, unavailable until first unlock, never synced to iCloud.
protocol TokenStore: Sendable {
    func read() -> String?
    func write(_ token: String) throws
    func delete()
}

struct KeychainTokenStore: TokenStore {
    let service = "art.marketingasart.shopline.session"
    let account = "maa-session"

    private var base: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: account]
    }

    func read() -> String? {
        var q = base
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func write(_ token: String) throws {
        delete()
        var q = base
        q[kSecValueData as String] = Data(token.utf8)
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(q as CFDictionary, nil)
        guard status == errSecSuccess else { throw NSError(domain: NSOSStatusErrorDomain, code: Int(status)) }
    }

    func delete() { SecItemDelete(base as CFDictionary) }
}

/// In-memory store for tests and previews.
final class MemoryTokenStore: TokenStore, @unchecked Sendable {
    private let lock = NSLock()
    private var token: String?
    init(_ token: String? = nil) { self.token = token }
    func read() -> String? { lock.withLock { token } }
    func write(_ t: String) throws { lock.withLock { token = t } }
    func delete() { lock.withLock { token = nil } }
}
