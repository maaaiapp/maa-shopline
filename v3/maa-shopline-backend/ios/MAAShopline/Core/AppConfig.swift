import Foundation

/// Build-time configuration read from Info.plist (populated from the xcconfig files).
struct AppConfig: Sendable {
    let apiBaseURL: URL
    let privacyPolicyURL: URL?
    static let callbackScheme = "maashopline"

    enum ConfigError: Error, Equatable { case missing(String), insecure(String) }

    static func load(from info: [String: Any] = Bundle.main.infoDictionary ?? [:],
                     requireHTTPS: Bool = !AppConfig.isDebug) throws -> AppConfig {
        guard let raw = info["MAAAPIBaseURL"] as? String, let url = URL(string: raw), url.host != nil else {
            throw ConfigError.missing("MAAAPIBaseURL")
        }
        if requireHTTPS && url.scheme != "https" { throw ConfigError.insecure(raw) }
        let privacy = (info["MAAPrivacyPolicyURL"] as? String).flatMap(URL.init(string:))
        return AppConfig(apiBaseURL: url, privacyPolicyURL: privacy)
    }

    static var isDebug: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }
}
