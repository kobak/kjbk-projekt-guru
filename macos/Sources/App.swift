import AppKit
import SwiftUI
import WebKit

@MainActor
final class GuruApp: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, WKDownloadDelegate {
    private var window: NSWindow!
    private var web: WKWebView!
    private var notifications: MacNotifications!
    private var status: NSStatusItem!
    private var settingsWindow: NSWindow?
    private var connectionItem: NSMenuItem!
    private var notificationItem: NSMenuItem!
    private var returnURL: URL?
    private var policy: ServerPolicy!
    private var downloads: [WKDownload] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        let info = Bundle.main.infoDictionary ?? [:]
        guard let raw = info["GURUServerURL"] as? String, let url = URL(string: raw),
              let valid = ServerPolicy(url: url, development: info["GURUDevelopment"] as? Bool == true) else {
            NSApp.presentError(NSError(domain: "GURU", code: 1, userInfo: [NSLocalizedDescriptionKey: "Érvénytelen GURU-szervercím."]))
            NSApp.terminate(nil)
            return
        }
        policy = valid
        notifications = MacNotifications(policy: valid)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
        let controller = configuration.userContentController
        controller.add(self, name: "guruMac")
        var originParts = URLComponents(url: valid.base, resolvingAgainstBaseURL: false)!
        if originParts.port == (originParts.scheme == "https" ? 443 : 80) { originParts.port = nil }
        originParts.path = ""
        let origin = originParts.url!.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let encodedOrigin = String(data: try! JSONEncoder().encode(origin), encoding: .utf8)!
        controller.addUserScript(WKUserScript(source: "if(location.origin===\(encodedOrigin)){window.guruMac={notificationsEnabled:false};}", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
        web.allowsMagnification = true
        web.underPageBackgroundColor = .windowBackgroundColor
        notifications.webView = web
        notifications.changed = { [weak self] in self?.updateStatus() }
        notifications.openNotice = { [weak self] task in
            guard let self = self else { return }
            self.showWindow()
            let path = task.flatMap { UUID(uuidString: $0) }.map { "/?task=\($0.uuidString.lowercased())" } ?? "/"
            self.web.load(URLRequest(url: self.policy.localURL(path)!))
        }
        makeWindow()
        makeMenu()
        makeStatusItem()
        web.load(URLRequest(url: valid.base))
        notifications.start()
        NotificationCenter.default.addObserver(self, selector: #selector(wokeUp), name: NSApplication.didBecomeActiveNotification, object: nil)
        NSWorkspace.shared.notificationCenter.addObserver(self, selector: #selector(wokeUp), name: NSWorkspace.didWakeNotification, object: nil)
        NSWorkspace.shared.notificationCenter.addObserver(self, selector: #selector(wokeUp), name: NSWorkspace.sessionDidBecomeActiveNotification, object: nil)
        showWindow()
    }
    private func makeWindow() {
        let area = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 820)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: min(1320, area.width - 50), height: min(900, area.height - 50)),
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        window.title = "kjbk projekt guru"
        window.subtitle = "Közös munkatér"
        window.minSize = NSSize(width: 850, height: 580)
        window.contentView = web
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.setFrameAutosaveName("GuruMainWindow")
        if !window.setFrameUsingName("GuruMainWindow") { window.center() }
        let toolbar = NSToolbar(identifier: "GuruToolbar")
        toolbar.delegate = self
        toolbar.displayMode = .iconOnly
        window.toolbar = toolbar
        window.toolbarStyle = .unified
    }
    private func item(_ title: String, _ action: Selector?, _ key: String = "", target: AnyObject? = nil) -> NSMenuItem {
        let result = NSMenuItem(title: title, action: action, keyEquivalent: key)
        result.target = target ?? self
        return result
    }
    private func makeMenu() {
        let main = NSMenu()
        let appMenu = NSMenu(title: "kjbk projekt guru")
        appMenu.addItem(item("A kjbk projekt guru névjegye", #selector(about)))
        appMenu.addItem(.separator())
        appMenu.addItem(item("Mac-beállítások…", #selector(settings), ","))
        appMenu.addItem(item("Fiók és csapat beállításai…", #selector(webSettings)))
        appMenu.addItem(.separator())
        appMenu.addItem(item("GURU elrejtése", #selector(NSApplication.hide(_:)), "h", target: NSApp))
        appMenu.addItem(item("Kilépés a GURU-ból", #selector(NSApplication.terminate(_:)), "q", target: NSApp))
        let file = NSMenu(title: "Fájl")
        file.addItem(item("Új feladat", #selector(newTask), "n"))
        file.addItem(item("Megnyitás böngészőben", #selector(openBrowser)))
        file.addItem(.separator())
        file.addItem(item("Ablak bezárása", #selector(closeWindow), "w"))
        let edit = NSMenu(title: "Szerkesztés")
        for (title, action, key) in [("Visszavonás", "undo:", "z"), ("Kivágás", "cut:", "x"), ("Másolás", "copy:", "c"), ("Beillesztés", "paste:", "v"), ("Összes kijelölése", "selectAll:", "a")] {
            let entry = NSMenuItem(title: title, action: Selector(action), keyEquivalent: key)
            edit.addItem(entry)
        }
        let view = NSMenu(title: "Nézet")
        view.addItem(item("Áttekintés", #selector(home)))
        view.addItem(item("Keresés", #selector(search), "k"))
        view.addItem(item("Frissítés", #selector(refresh), "r"))
        view.addItem(item("Vissza", #selector(back), "["))
        view.addItem(item("Előre", #selector(forward), "]"))
        let windows = NSMenu(title: "Ablak")
        windows.addItem(item("GURU megnyitása", #selector(showWindow)))
        windows.addItem(NSMenuItem(title: "Kis méret", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m"))
        let help = NSMenu(title: "Súgó")
        help.addItem(item("Mac használati útmutató", #selector(helpPage)))
        for menu in [appMenu, file, edit, view, windows, help] {
            let parent = NSMenuItem()
            parent.submenu = menu
            main.addItem(parent)
        }
        NSApp.mainMenu = main
        NSApp.windowsMenu = windows
    }
    private func makeStatusItem() {
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        status.button?.image = NSImage(systemSymbolName: "checklist", accessibilityDescription: "kjbk projekt guru")
        status.button?.imagePosition = .imageLeading
        let menu = NSMenu()
        menu.addItem(item("GURU megnyitása", #selector(showWindow)))
        menu.addItem(item("Új feladat", #selector(newTask)))
        menu.addItem(.separator())
        connectionItem = item("Jelentkezz be a GURU-ba.", nil)
        menu.addItem(connectionItem)
        notificationItem = item("Értesítések bekapcsolása…", #selector(toggleNotifications))
        menu.addItem(notificationItem)
        menu.addItem(item("Próbaértesítés", #selector(testNotification)))
        menu.addItem(item("Mac-beállítások…", #selector(settings)))
        menu.addItem(.separator())
        menu.addItem(item("Kilépés", #selector(NSApplication.terminate(_:)), target: NSApp))
        status.menu = menu
    }
    private func updateStatus() {
        guard status != nil else { return }
        let count = notifications.unread
        status.button?.title = count > 0 ? " \(min(count, 99))\(count > 99 ? "+" : "")" : ""
        status.button?.toolTip = count > 0 ? "\(count) olvasatlan GURU-értesítés" : "kjbk projekt guru"
        NSApp.dockTile.badgeLabel = count > 0 ? String(count) : nil
        connectionItem.title = notifications.stateText
        notificationItem.title = notifications.enabled ? "Értesítések kikapcsolása" : "Értesítések bekapcsolása…"
    }
    @objc func showWindow() { window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true) }
    @objc private func closeWindow() { NSApp.keyWindow?.performClose(nil) }
    @objc private func home() { showWindow(); web.load(URLRequest(url: policy.base)) }
    @objc private func refresh() {
        if let target = returnURL { returnURL = nil; web.load(URLRequest(url: target)) }
        else { web.reload() }
        Task { await notifications.poll() }
    }
    @objc private func back() { web.goBack() }
    @objc private func forward() { web.goForward() }
    private func webCommand(_ name: String) {
        showWindow()
        let literal = String(data: try! JSONEncoder().encode(name), encoding: .utf8)!
        web.evaluateJavaScript("window.dispatchEvent(new CustomEvent('guru-mac-command',{detail:\(literal)}));", completionHandler: nil)
    }
    @objc private func newTask() { webCommand("new-task") }
    @objc private func search() { webCommand("search") }
    @objc private func webSettings() { webCommand("settings") }
    @objc private func toggleNotifications() { notifications.toggle() }
    @objc private func testNotification() { notifications.testNotification() }
    @objc private func wokeUp() { Task { await notifications.updatePermission(); await notifications.poll() } }
    @objc private func openBrowser() { NSWorkspace.shared.open(returnURL ?? web.url ?? policy.base) }
    @objc private func about() {
        NSApp.orderFrontStandardAboutPanel(options: [NSApplication.AboutPanelOptionKey.applicationName: "kjbk projekt guru",
            NSApplication.AboutPanelOptionKey.applicationVersion: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "",
            NSApplication.AboutPanelOptionKey.credits: NSAttributedString(string: "Közös célok. Mac-en is.\nKJBK Infinity Kft. · MIT-licencű forráskód.")])
    }
    @objc private func helpPage() { NSWorkspace.shared.open(URL(string: "https://github.com/kobak/kjbk-projekt-guru/blob/main/docs/mac-app.md")!) }
    @objc private func settings() {
        if settingsWindow == nil {
            let controller = NSHostingController(rootView: MacSettings(model: notifications))
            let panel = NSWindow(contentViewController: controller)
            panel.title = "GURU · Mac-beállítások"
            panel.styleMask = [.titled, .closable]
            panel.setContentSize(NSSize(width: 540, height: 380))
            panel.isReleasedWhenClosed = false
            panel.center()
            settingsWindow = panel
        }
        settingsWindow?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { showWindow(); return true }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        Task { await notifications.updatePermission(); await notifications.poll() }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        let alert = NSAlert()
        alert.messageText = "A GURU most nem érhető el"
        alert.informativeText = "Ellenőrizd az internetkapcsolatot. A Frissítés (⌘R) gombbal újrapróbálhatod."
        alert.beginSheetModal(for: window)
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if policy.isOwn(url) {
            if url.path == "/api/google/connect/" {
                NSWorkspace.shared.open(policy.localURL("/?settings=1")!)
                returnURL = policy.localURL("/?settings=1")
                decisionHandler(.cancel)
            } else if navigationAction.shouldPerformDownload { decisionHandler(.download) }
            else { decisionHandler(.allow) }
        } else {
            // Only user-initiated external links may open another application.
            if navigationAction.navigationType == .linkActivated, ["https", "http", "mailto"].contains(url.scheme ?? "") {
                NSWorkspace.shared.open(url)
            }
            decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
        decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if !navigationResponse.canShowMIMEType || (navigationResponse.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")?.lowercased().hasPrefix("attachment") == true {
            decisionHandler(.download)
        } else { decisionHandler(.allow) }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, navigationAction.navigationType == .linkActivated,
           ["https", "http"].contains(url.scheme ?? "") {
            if policy.isOwn(url) { web.load(URLRequest(url: url)) }
            else { NSWorkspace.shared.open(url) }
        }
        return nil
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "Igen")
        alert.addButton(withTitle: "Mégse")
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, let origin = message.frameInfo.request.url, policy.isOwn(origin),
              let payload = message.body as? [String: Any], let command = payload["command"] as? String else { return }
        switch command {
        case "notifications": notifications.toggle()
        case "settings": settings()
        case "browser":
            if let path = payload["path"] as? String, let url = policy.localURL(path) {
                returnURL = url
                NSWorkspace.shared.open(url)
            }
        default: break
        }
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        downloads.append(download); download.delegate = self
    }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        downloads.append(download); download.delegate = self
    }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String,
        completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = (suggestedFilename as NSString).lastPathComponent
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.url : nil) }
    }
    func downloadDidFinish(_ download: WKDownload) { downloads.removeAll { $0 === download } }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        downloads.removeAll { $0 === download }
    }
}

extension GuruApp: NSToolbarDelegate {
    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] { toolbarDefaultItemIdentifiers(toolbar) }
    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        var items = ["home", "back", "forward", "refresh", "search", "new", "browser", "settings"].map { NSToolbarItem.Identifier($0) }
        items.insert(.flexibleSpace, at: 4)
        return items
    }
    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier identifier: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        let specs: [String: (String, String, Selector)] = [
            "home": ("Áttekintés", "house", #selector(home)), "back": ("Vissza", "chevron.left", #selector(back)),
            "forward": ("Előre", "chevron.right", #selector(forward)), "refresh": ("Frissítés · ⌘R", "arrow.clockwise", #selector(refresh)),
            "search": ("Keresés · ⌘K", "magnifyingglass", #selector(search)), "new": ("Új feladat · ⌘N", "plus", #selector(newTask)),
            "browser": ("Megnyitás böngészőben", "safari", #selector(openBrowser)), "settings": ("Mac-beállítások · ⌘,", "gearshape", #selector(settings))]
        guard let (label, image, action) = specs[identifier.rawValue] else { return nil }
        let result = NSToolbarItem(itemIdentifier: identifier)
        result.label = label; result.toolTip = label
        result.image = NSImage(systemSymbolName: image, accessibilityDescription: label)
        result.target = self; result.action = action
        return result
    }
}

private struct MacSettings: View {
    @ObservedObject var model: MacNotifications
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 14) {
                Image(nsImage: NSApp.applicationIconImage).resizable().frame(width: 56, height: 56)
                VStack(alignment: .leading, spacing: 3) {
                    Text("kjbk projekt guru").font(.title2.weight(.semibold))
                    Text("Mac · \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "")").foregroundStyle(.secondary)
                }
            }
            Divider()
            Toggle("Natív Mac-értesítések", isOn: Binding(get: { model.enabled }, set: { _ in model.toggle() }))
            Text(model.permissionText).font(.callout).foregroundStyle(.secondary)
            HStack { Text(model.stateText).font(.callout); Spacer(); Button("Próbaértesítés") { model.testNotification() }.disabled(!model.enabled) }
            Text("Az ablak bezárása után a GURU a menüsorban fut tovább, és 15 másodpercenként ellenőrzi az új értesítéseket. A Kilépés leállítja. Alvó vagy internet nélküli Mac-en a jelzések késhetnek.")
                .font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            Text("Az értesítések típusait a GURU Beállítások → Értesítések részének Push oszlopában választhatod ki.")
                .font(.callout).fixedSize(horizontal: false, vertical: true)
        }.padding(26).frame(width: 540)
    }
}

@main
enum Main {
    @MainActor static func main() {
        let app = NSApplication.shared
        let delegate = GuruApp()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        withExtendedLifetime(delegate) { app.run() }
    }
}
