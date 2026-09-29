import SwiftUI

struct AdvisorView: View {
    @Environment(AppModel.self) private var model
    @State private var question = ""
    @State private var arabic = false
    @State private var busy = false
    @State private var result: AdvisorResponse?
    @State private var jobState: String?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Ask about your store's marketing", text: $question, axis: .vertical)
                        .lineLimit(3...6)
                    Toggle("Answer in Arabic", isOn: $arabic)
                    Button {
                        Task { await ask() }
                    } label: {
                        HStack { Text("Ask"); if busy { Spacer(); ProgressView() } }
                    }
                    .disabled(busy || question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } footer: {
                    Text("Your question is processed by MAA and only sent to AI providers approved for store data.")
                }
                if let error { Section { Label(error, systemImage: "exclamationmark.triangle") } }
                if let result { Section("Answer") { AnswerView(result: result, jobState: jobState) } }
            }
            .navigationTitle("Growth Advisor")
            .environment(\.layoutDirection, arabic ? .rightToLeft : .leftToRight)
        }
    }

    private func ask() async {
        guard let api = model.api else { return }
        busy = true; error = nil; result = nil; jobState = nil
        defer { busy = false }
        do {
            let r = try await api.ask(question.trimmingCharacters(in: .whitespacesAndNewlines), arabic: arabic)
            result = r
            if r.state == "queued", let id = r.jobId { await poll(id, api: api) }
        } catch APIError.unauthenticated {
            model.signOut()
        } catch APIError.network {
            error = "You appear to be offline."
        } catch {
            error = "Couldn't send your question. Please try again."
        }
    }

    /// Polls a queued job with backoff for up to ~2 minutes; after that the job keeps running server-side.
    private func poll(_ id: String, api: APIClient) async {
        for delay in [3, 5, 10, 15, 30, 60] {
            try? await Task.sleep(for: .seconds(delay))
            guard let s = try? await api.job(id) else { continue }
            jobState = s.state
            if s.state != "preparing" { return }
        }
    }
}

struct AnswerView: View {
    let result: AdvisorResponse
    let jobState: String?

    var body: some View {
        switch result.state {
        case "live":
            Text(result.answer?.displayText ?? "")
        case "last_valid":
            VStack(alignment: .leading, spacing: 6) {
                Text(result.answer?.displayText ?? "")
                if let d = result.generatedAt { Text("From \(Self.friendly(d)), refreshing").font(.footnote).foregroundStyle(.secondary) }
            }
        case "queued":
            switch jobState {
            case "ready": Label("Ready: ask again to see the answer.", systemImage: "checkmark.circle")
            case "not_computed": NotComputedChip()
            default: Label("Being prepared. This can take a few minutes.", systemImage: "clock")
            }
        default:
            NotComputedChip()
        }
    }

    static func friendly(_ iso: String) -> String {
        guard let d = ISO8601DateFormatter().date(from: iso) else { return iso }
        return d.formatted(date: .abbreviated, time: .shortened)
    }
}
