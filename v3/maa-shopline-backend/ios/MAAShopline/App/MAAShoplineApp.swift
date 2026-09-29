import SwiftUI

@main
struct MAAShoplineApp: App {
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .task { await model.start() }
        }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        switch model.phase {
        case .launching: ProgressView()
        case .misconfigured(let msg): ContentUnavailableView("Unavailable", systemImage: "wrench.and.screwdriver", description: Text(msg))
        case .signedOut: ConnectView()
        case .signedIn: MainTabs()
        }
    }
}

struct MainTabs: View {
    var body: some View {
        TabView {
            HealthCheckView().tabItem { Label("Health", systemImage: "waveform.path.ecg") }
            AdvisorView().tabItem { Label("Advisor", systemImage: "bubble.left.and.text.bubble.right") }
            SettingsView().tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
