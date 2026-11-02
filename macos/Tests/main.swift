import Foundation

func check(_ value: @autoclosure () -> Bool, _ message: String) {
    if !value() { fatalError(message) }
}
let production = ServerPolicy(url: URL(string: "https://a.kjbk.hu")!)!
check(production.isOwn(URL(string: "https://a.kjbk.hu:443/?task=abc")!), "same HTTPS origin")
check(!production.isOwn(URL(string: "https://a.kjbk.hu.evil.example/")!), "lookalike host")
check(!production.isOwn(URL(string: "https://a.kjbk.hu:8443/")!), "different port")
check(!production.isOwn(URL(string: "http://a.kjbk.hu/")!), "HTTPS downgrade")
check(production.localURL("//evil.example") == nil, "network-path reference")
check(production.localURL("/\\evil.example") == nil, "backslash authority")
check(ServerPolicy(url: URL(string: "http://a.kjbk.hu")!, development: true) == nil, "development cannot allow public HTTP")
check(ServerPolicy(url: URL(string: "http://127.0.0.1:8000")!, development: true) != nil, "explicit loopback development")
check(ServerPolicy(url: URL(string: "https://secret@example.com")!) == nil, "no embedded credentials")
check(ServerPolicy(url: URL(string: "https://a.kjbk.hu/?invite=secret")!) == nil, "no secret launch query")
let first = try! JSONDecoder().decode(NotificationFeed.self, from: Data("""
{"user_id":1,"cursor":25,"unread":2,"has_more":false,"notifications":[]}
""".utf8))
var tracker = FeedTracker()
tracker.baseline(first, savedCursor: nil)
check(tracker.cursor == 25, "first login baselines without backlog")
tracker.baseline(first, savedCursor: 12)
check(tracker.cursor == 12, "restart resumes own saved cursor")
tracker.baseline(first, savedCursor: 999)
check(tracker.cursor == 25, "restored database cannot strand cursor in future")
tracker.baseline(first, savedCursor: 12)
let other = try! JSONDecoder().decode(NotificationFeed.self, from: Data("""
{"user_id":2,"cursor":30,"unread":0,"has_more":false,"notifications":[]}
""".utf8))
check(!tracker.accepts(other), "account switch never delivers previous account's batch")
tracker.acknowledge(other)
check(tracker.cursor == 12, "wrong account cannot advance delivery cursor")
tracker.acknowledge(first)
check(tracker.cursor == 25, "successful delivery advances cursor")
tracker.reset()
check(tracker.userID == nil && tracker.cursor == nil, "logout clears account state")
print("Mac protocol: 17 checks passed")
