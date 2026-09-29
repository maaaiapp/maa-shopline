import Foundation

/// Any JSON value. AI outputs are structured per task; the UI renders them generically.
enum JSONValue: Codable, Equatable, Sendable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }

    /// Readable text for display: strings as-is, objects as "key: value" lines.
    var displayText: String {
        switch self {
        case .string(let s): return s
        case .number(let n): return n.rounded() == n ? String(Int(n)) : String(n)
        case .bool(let b): return b ? "Yes" : "No"
        case .null: return ""
        case .array(let a): return a.map { "• " + $0.displayText }.joined(separator: "\n")
        case .object(let o):
            return o.keys.sorted().map { k in "\(k.replacingOccurrences(of: "_", with: " ").capitalized): \(o[k]!.displayText)" }
                .joined(separator: "\n")
        }
    }
}

struct Connection: Decodable, Equatable, Sendable {
    let state: String            // connected | token_expired | disconnected
    let scopes: [String]?
    let capabilities: [String: String]?
}

struct HealthDimension: Decodable, Equatable, Identifiable, Sendable {
    let key: String
    let state: String            // scored | unscored | insufficient
    let score: Int?
    let needs: String?
    var id: String { key }
}

struct HealthResult: Decodable, Equatable, Sendable {
    let overall: Int?
    let bindingConstraint: String?
    let maintenance: Bool?
    let coverage: String
    let dimensions: [HealthDimension]
    enum CodingKeys: String, CodingKey { case overall, maintenance, coverage, dimensions, bindingConstraint = "binding_constraint" }
}

struct HealthCheckResponse: Decodable, Equatable, Sendable {
    let state: String            // live | degraded
    let result: HealthResult
}

/// Gateway outcome. The four states of the never-error ladder, plus not_computed.
struct AdvisorResponse: Decodable, Equatable, Sendable {
    let state: String            // live | last_valid | queued | not_computed | blocked
    let answer: JSONValue?
    let generatedAt: String?
    let jobId: String?
    let reason: String?
    enum CodingKeys: String, CodingKey { case state, answer, reason, generatedAt = "generated_at", jobId = "job_id" }
}

struct JobStatus: Decodable, Equatable, Sendable { let state: String }   // preparing | ready | not_computed
struct SessionResponse: Decodable, Sendable { let session: String }
struct DeleteResponse: Decodable, Sendable { let deleted: Bool; let next: String? }
