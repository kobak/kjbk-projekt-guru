import XCTest

final class GuruUITests: XCTestCase {
    // iPad windowing and Focus can put a notice straight into Notification Center.
    @MainActor
    private func findNotice(_ text: String, on system: XCUIApplication) -> XCUIElement {
        let notice = system.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
        if notice.waitForExistence(timeout: 5) { return notice }
        let top = system.coordinate(withNormalizedOffset: CGVector(dx: 0.42, dy: 0.002))
        let bottom = system.coordinate(withNormalizedOffset: CGVector(dx: 0.42, dy: 0.80))
        top.press(forDuration: 0.1, thenDragTo: bottom)
        return notice
    }

    @MainActor
    func testWorkspaceAndPush() async throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchEnvironment["GURU_SIMULATOR_URL"] = "http://127.0.0.1:8021"
        app.launch()
        let menu = app.buttons["GURU menü"]
        XCTAssertTrue(menu.waitForExistence(timeout: 15))
        let workspace = app.webViews.firstMatch
        let login = workspace.buttons["Belépés a munkatérbe"]
        let newTask = workspace.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", "Új feladat")).firstMatch
        if login.waitForExistence(timeout: 8) {
            workspace.textFields.firstMatch.tap()
            workspace.textFields.firstMatch.typeText("demo@kozos.local")
            let password = workspace.secureTextFields.firstMatch
            password.tap()
            password.typeText("Kozos-demo-2026!\n")
        }
        XCTAssertTrue(newTask.waitForExistence(timeout: 20), app.debugDescription)
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "GURU munkatér"
        shot.lifetime = .keepAlways
        add(shot)

        menu.tap()
        app.buttons["Helyi próbaértesítés"].tap()
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let allow = springboard.buttons.matching(NSPredicate(format: "label IN %@", ["Allow", "Engedélyezés"])).firstMatch
        if allow.waitForExistence(timeout: 3) { allow.tap() }
        let local = findNotice("Megérkezett a helyi próbaértesítés", on: springboard)
        XCTAssertTrue(local.waitForExistence(timeout: 12), springboard.debugDescription)

        // The loopback fixture delivers a real Simulator push to this test device.
        local.tap()
        app.activate()
        XCUIDevice.shared.press(.home)
        let url = URL(string: "http://127.0.0.1:8022/push")!
        let (_, response) = try await URLSession.shared.data(from: url)
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        let remote = findNotice("GURU távoli próba", on: springboard)
        XCTAssertTrue(remote.waitForExistence(timeout: 15), springboard.debugDescription)
        let taskTitle = workspace.textFields.matching(NSPredicate(format: "value == %@", "Szimulátoros push megnyitása")).firstMatch
        remote.tap()
        if !taskTitle.waitForExistence(timeout: 5) {
            // A first tap on grouped notices expands the stack on iPad.
            let open = springboard.buttons.matching(NSPredicate(format: "label IN %@", ["Open", "Megnyitás"])).firstMatch
            if open.exists { open.tap() } else if remote.exists { remote.tap() }
        }
        XCTAssertTrue(taskTitle.waitForExistence(timeout: 15), app.debugDescription + springboard.debugDescription)
    }
}
