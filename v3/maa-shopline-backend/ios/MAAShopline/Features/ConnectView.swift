import SwiftUI

struct ConnectView: View {
    @Environment(AppModel.self) private var model
    @State private var handle = ""
    @State private var busy = false
    @State private var message: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("your-store", text: $handle)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .accessibilityLabel("SHOPLINE store handle")
                } header: {
                    Text("SHOPLINE store")
                } footer: {
                    Text("The part before .myshopline.com. You'll approve access on SHOPLINE's own page.")
                }
                Section {
                    Button {
                        Task { await connect() }
                    } label: {
                        HStack { Text("Connect store"); if busy { Spacer(); ProgressView() } }
                    }
                    .disabled(busy || !AuthService.isValidHandle(normalized))
                }
                if let message { Section { Text(message).foregroundStyle(.secondary) } }
            }
            .navigationTitle("MAA for SHOPLINE")
        }
    }

    private var normalized: String { handle.trimmingCharacters(in: .whitespaces).lowercased() }

    private func connect() async {
        guard let cfg = model.config else { return }
        busy = true; message = nil
        defer { busy = false }
        do {
            let token = try await AuthService(config: cfg).signIn(handle: normalized)
            await model.completeSignIn(token: token)
        } catch AuthError.cancelled {
            message = nil
        } catch AuthError.invalidHandle {
            message = "Enter the store handle only, e.g. my-store."
        } catch {
            message = "Couldn't connect right now. Please try again."
        }
    }
}
