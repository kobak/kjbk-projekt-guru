import UIKit
import UserNotifications

@MainActor
final class Push {
    static let shared = Push()
    private let center = UNUserNotificationCenter.current()
    private var waiters = [CheckedContinuation<Data, Error>]()
    private var registration: UUID?

    func reply(prompt: Bool) async throws -> [String: String] {
        var status = await center.notificationSettings().authorizationStatus
        if prompt && status == .notDetermined {
            _ = try await center.requestAuthorization(options: [.alert, .sound])
            status = await center.notificationSettings().authorizationStatus
        }
        guard [.authorized, .provisional, .ephemeral].contains(status) else {
            return ["permission": status == .denied ? "denied" : "undetermined"]
        }
        let token = try await deviceToken()
        let env = Bundle.main.object(forInfoDictionaryKey: "GURUAPSEnvironment") as? String
        return ["permission": "granted", "token": token.map { String(format: "%02x", $0) }.joined(),
                "environment": env == "production" ? "production" : "sandbox"]
    }

    private func deviceToken() async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            waiters.append(continuation)
            guard registration == nil else { return }
            let attempt = UUID()
            registration = attempt
            UIApplication.shared.registerForRemoteNotifications()
            Task {
                try? await Task.sleep(for: .seconds(15))
                if registration == attempt { finish(.failure(URLError(.timedOut))) }
            }
        }
    }

    func finish(_ result: Result<Data, Error>) {
        let pending = waiters
        waiters.removeAll()
        registration = nil
        pending.forEach { $0.resume(with: result) }
    }

    func sample() async throws {
        guard try await center.requestAuthorization(options: [.alert, .sound]) else {
            throw NSError(domain: "GURU", code: 1, userInfo: [NSLocalizedDescriptionKey:
                "Engedélyezd a GURU értesítéseit a készülék Beállítások alkalmazásában."])
        }
        let content = UNMutableNotificationContent()
        content.title = "GURU"
        content.body = "Megérkezett a helyi próbaértesítés."
        content.sound = .default
        try await center.add(UNNotificationRequest(identifier: "guru-local-test", content: content,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: 2, repeats: false)))
    }
}
