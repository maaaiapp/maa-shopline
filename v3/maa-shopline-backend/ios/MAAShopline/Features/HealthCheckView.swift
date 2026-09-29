import SwiftUI

struct HealthCheckView: View {
    @Environment(AppModel.self) private var model
    @State private var state: Loadable<HealthCheckResponse> = .idle

    var body: some View {
        NavigationStack {
            content
                .navigationTitle("Marketing Health")
                .refreshable { await load() }
                .task { if state == .idle { await load() } }
        }
    }

    @ViewBuilder private var content: some View {
        switch state {
        case .idle, .loading:
            ProgressView("Loading…")
        case .failed(let msg):
            ContentUnavailableView {
                Label("Not available", systemImage: "wifi.exclamationmark")
            } description: { Text(msg) } actions: { Button("Retry") { Task { await load() } } }
        case .empty(let msg):
            ContentUnavailableView("Nothing yet", systemImage: "chart.bar", description: Text(msg))
        case .loaded(let hc):
            List {
                Section {
                    HStack {
                        Text("Overall")
                        Spacer()
                        if let o = hc.result.overall { Text("\(o)").font(.title2.bold()) } else { NotComputedChip() }
                    }
                    Text("Scored \(hc.result.coverage) dimensions").foregroundStyle(.secondary)
                    if hc.state == "degraded" {
                        Label("Store data access is not enabled yet, so scores are not computed.", systemImage: "info.circle")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
                Section("Dimensions") {
                    ForEach(hc.result.dimensions) { d in
                        HStack {
                            Text(d.key.replacingOccurrences(of: "_", with: " ").capitalized)
                            Spacer()
                            if let s = d.score { Text("\(s)") } else { NotComputedChip() }
                        }
                    }
                }
            }
        }
    }

    private func load() async {
        guard let api = model.api else { return }
        if case .loaded = state {} else { state = .loading }
        do {
            let hc = try await api.healthCheck()
            state = hc.result.dimensions.isEmpty ? .empty("No dimensions returned.") : .loaded(hc)
        } catch APIError.unauthenticated {
            model.signOut()
        } catch APIError.network {
            state = .failed("You appear to be offline.")
        } catch {
            state = .failed("The health check couldn't load. Please try again.")
        }
    }
}

/// The plan's "honest gap": a value that was not computed is labelled, never estimated.
struct NotComputedChip: View {
    var body: some View {
        Text("NOT COMPUTED")
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(.secondary.opacity(0.15), in: Capsule())
            .accessibilityLabel("Not computed")
    }
}
