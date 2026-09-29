import SwiftUI

struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @State private var confirmDelete = false
    @State private var deleting = false
    @State private var deleteFailed = false

    var body: some View {
        NavigationStack {
            List {
                Section("Store") {
                    LabeledContent("Connection", value: label(model.connection?.state))
                    if let scopes = model.connection?.scopes, !scopes.isEmpty {
                        LabeledContent("Access", value: scopes.joined(separator: ", "))
                    }
                    Button("Refresh") { Task { await model.refreshConnection() } }
                }
                Section("Privacy") {
                    if let url = model.config?.privacyPolicyURL { Link("Privacy policy", destination: url) }
                }
                Section {
                    Button("Log out") { model.signOut() }
                    Button("Delete account and data", role: .destructive) { confirmDelete = true }
                        .disabled(deleting)
                } footer: {
                    Text("Deleting removes your MAA data and the stored SHOPLINE access token. To fully disconnect, also uninstall the app in your SHOPLINE admin.")
                }
            }
            .navigationTitle("Settings")
            .confirmationDialog("Delete your account and all MAA data?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Delete", role: .destructive) {
                    Task { deleting = true; deleteFailed = !(await model.deleteAccount()); deleting = false }
                }
            } message: { Text("This can't be undone.") }
            .alert("Couldn't delete right now", isPresented: $deleteFailed) { Button("OK", role: .cancel) {} }
        }
    }

    private func label(_ s: String?) -> String {
        switch s {
        case "connected": "Connected"
        case "token_expired": "Reconnect needed"
        case .none: "Checking…"
        default: "Disconnected"
        }
    }
}
