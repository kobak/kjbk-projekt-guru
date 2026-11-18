import UIKit
import WebKit

final class WorkspaceController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandlerWithReply, WKDownloadDelegate {
    private let policy: ServerPolicy = {
        #if DEBUG && targetEnvironment(simulator)
        if let raw = ProcessInfo.processInfo.environment["GURU_SIMULATOR_URL"], let url = URL(string: raw),
           ["127.0.0.1", "localhost"].contains(url.host), let local = ServerPolicy(url: url, development: true) {
            return local
        }
        #endif
        guard let raw = Bundle.main.object(forInfoDictionaryKey: "GURUServerURL") as? String,
              let url = URL(string: raw), let policy = ServerPolicy(url: url) else {
            preconditionFailure("Hibás GURUServerURL")
        }
        return policy
    }()
    private var web: WKWebView!
    private var currentURL: URL?
    private var downloads: [ObjectIdentifier: URL] = [:]

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "GURU"
        view.backgroundColor = .systemBackground
        let config = WKWebViewConfiguration()
        config.applicationNameForUserAgent = "GURUMobile/0.1"
        config.userContentController.addScriptMessageHandler(self, contentWorld: .page, name: "guruMobile")
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.translatesAutoresizingMaskIntoConstraints = false
        web.allowsBackForwardNavigationGestures = true
        view.addSubview(web)
        let safe = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([web.topAnchor.constraint(equalTo: safe.topAnchor), web.bottomAnchor.constraint(equalTo: safe.bottomAnchor),
                                     web.leadingAnchor.constraint(equalTo: safe.leadingAnchor), web.trailingAnchor.constraint(equalTo: safe.trailingAnchor)])
        let menu = UIMenu(children: [
            UIAction(title: "Értesítési beállítások", image: UIImage(systemName: "bell")) { [weak self] _ in
                self?.load(path: "/?settings=notifications")
            },
            UIAction(title: "Helyi próbaértesítés", image: UIImage(systemName: "bell.badge")) { [weak self] _ in
                Task {
                    do { try await Push.shared.sample() }
                    catch { self?.message("Próbaértesítés", error.localizedDescription) }
                }
            },
            UIAction(title: "Rendszerértesítések beállításai", image: UIImage(systemName: "gear")) { _ in
                if let url = URL(string: UIApplication.openNotificationSettingsURLString) { UIApplication.shared.open(url) }
            },
            UIAction(title: "Frissítés", image: UIImage(systemName: "arrow.clockwise")) { [weak self] _ in self?.refresh() },
        ])
        let more = UIBarButtonItem(image: UIImage(systemName: "ellipsis.circle"), menu: menu)
        more.accessibilityLabel = "GURU menü"
        navigationItem.rightBarButtonItem = more
        load(path: "/")
    }

    func disconnect() {
        web?.configuration.userContentController.removeScriptMessageHandler(forName: "guruMobile", contentWorld: .page)
    }

    func openTask(_ id: UUID) {
        loadViewIfNeeded()
        load(path: "/?task=" + id.uuidString.lowercased())
    }
    private func load(path: String) {
        guard let url = policy.localURL(path) else { return }
        currentURL = url
        web.load(URLRequest(url: url))
    }
    private func refresh() {
        if web.url != nil { web.reload() } else if let url = currentURL { web.load(URLRequest(url: url)) } else { load(path: "/") }
    }
    private func message(_ title: String, _ text: String, retry: Bool = false) {
        guard presentedViewController == nil else { return }
        let dialog = UIAlertController(title: title, message: text, preferredStyle: .alert)
        if retry { dialog.addAction(UIAlertAction(title: "Újra", style: .default) { [weak self] _ in self?.refresh() }) }
        dialog.addAction(UIAlertAction(title: "Bezárás", style: .cancel))
        present(dialog, animated: true)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if NavigationFailurePolicy.shouldReport(error) { message("A GURU nem érhető el", "Ellenőrizd az internetkapcsolatot, majd próbáld újra.", retry: true) }
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { refresh() }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if policy.isOwn(url) {
            if url.path == "/api/google/connect/" {
                if let settings = policy.localURL("/?settings=1") { UIApplication.shared.open(settings) }
                decisionHandler(.cancel)
            } else if policy.isDownload(url) || action.shouldPerformDownload {
                decisionHandler(.download)
            } else {
                decisionHandler(.allow)
            }
        } else {
            if action.navigationType == .linkActivated, ["https", "mailto", "tel"].contains(url.scheme ?? "") {
                UIApplication.shared.open(url)
            }
            decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url, policy.isOwn(url), action.navigationType == .linkActivated {
            if policy.isDownload(url) { webView.startDownload(using: action.request) { $0.delegate = self } }
            else { webView.load(action.request) }
        }
        return nil
    }
    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        guard let url = response.response.url, policy.isOwn(url) else { decisionHandler(.cancel); return }
        let disposition = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
        decisionHandler(!response.canShowMIMEType || disposition.lowercased().hasPrefix("attachment") ? .download : .allow)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                  decisionHandler: @escaping (WKDownload.RedirectPolicy) -> Void) {
        decisionHandler(request.url.map(policy.isOwn) == true ? .allow : .cancel)
    }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String,
                  completionHandler: @escaping (URL?) -> Void) {
        guard response.url.map(policy.isOwn) == true, (response as? HTTPURLResponse)?.statusCode == 200 else {
            completionHandler(nil); return
        }
        do {
            let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false)
            let name = (suggestedFilename as NSString).lastPathComponent
            let url = folder.appendingPathComponent(["", "/", ".", ".."].contains(name) ? "GURU-fájl" : name)
            downloads[ObjectIdentifier(download)] = url
            completionHandler(url)
        } catch { completionHandler(nil); message("A letöltés nem sikerült", error.localizedDescription) }
    }
    func downloadDidFinish(_ download: WKDownload) {
        guard let url = downloads.removeValue(forKey: ObjectIdentifier(download)) else { return }
        let share = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        share.popoverPresentationController?.barButtonItem = navigationItem.rightBarButtonItem
        share.completionWithItemsHandler = { _, _, _, _ in try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }
        present(share, animated: true)
    }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        if let url = downloads.removeValue(forKey: ObjectIdentifier(download)) { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }
        if NavigationFailurePolicy.shouldReport(error) { message("A letöltés nem sikerült", error.localizedDescription) }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage text: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard frame.isMainFrame, frame.request.url.map(policy.isOwn) == true, presentedViewController == nil else { completionHandler(false); return }
        let dialog = UIAlertController(title: "GURU", message: text, preferredStyle: .alert)
        dialog.addAction(UIAlertAction(title: "Mégse", style: .cancel) { _ in completionHandler(false) })
        dialog.addAction(UIAlertAction(title: "Rendben", style: .default) { _ in completionHandler(true) })
        present(dialog, animated: true)
    }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage,
                               replyHandler: @escaping (Any?, String?) -> Void) {
        guard message.webView === web, message.frameInfo.isMainFrame, message.frameInfo.request.url.map(policy.isOwn) == true,
              let values = message.body as? [String: String] else { replyHandler(nil, "Ismeretlen forrás."); return }
        switch values["command"] {
        case "enable", "renew":
            Task {
                do { replyHandler(try await Push.shared.reply(prompt: values["command"] == "enable"), nil) }
                catch { replyHandler(nil, "Az Apple push regisztrációja nem sikerült. Próbáld újra később.") }
            }
        case "browser":
            guard let path = values["path"], let url = policy.localURL(path) else { replyHandler(nil, "Érvénytelen hivatkozás."); return }
            UIApplication.shared.open(url)
            replyHandler([:], nil)
        default: replyHandler(nil, "Ismeretlen művelet.")
        }
    }
}
