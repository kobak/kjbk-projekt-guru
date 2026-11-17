import UIKit
import UserNotifications

@main
final class AppDelegate: UIResponder, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    weak var workspace: WorkspaceController?
    private var pendingTask: UUID?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken token: Data) {
        Push.shared.finish(.success(token))
    }
    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        Push.shared.finish(.failure(error))
    }
    func attach(_ controller: WorkspaceController) {
        workspace = controller
        if let pendingTask { controller.openTask(pendingTask); self.pendingTask = nil }
    }
    func open(_ response: UNNotificationResponse) {
        guard response.actionIdentifier == UNNotificationDefaultActionIdentifier,
              let raw = response.notification.request.content.userInfo["task_id"] as? String,
              let id = UUID(uuidString: raw) else { return }
        if let workspace { workspace.openTask(id) } else { pendingTask = id }
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        open(response)
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }
}

final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?
    func sceneDidDisconnect(_ scene: UIScene) {
        let navigation = window?.rootViewController as? UINavigationController
        (navigation?.viewControllers.first as? WorkspaceController)?.disconnect()
        window = nil
    }
    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let scene = scene as? UIWindowScene, let app = UIApplication.shared.delegate as? AppDelegate else { return }
        let controller = WorkspaceController()
        let window = UIWindow(windowScene: scene)
        window.rootViewController = UINavigationController(rootViewController: controller)
        self.window = window
        window.makeKeyAndVisible()
        app.attach(controller)
        if let response = connectionOptions.notificationResponse { app.open(response) }
    }
}
