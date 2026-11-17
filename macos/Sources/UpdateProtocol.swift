import Foundation

struct MacVersion: Comparable {
    let text: String
    private let parts: [Int]
    init?(_ text: String) {
        guard text.range(of: "\\A[0-9]{1,5}\\.[0-9]{1,5}\\.[0-9]{1,5}\\z", options: .regularExpression) != nil else { return nil }
        self.text = text
        parts = text.split(separator: ".").compactMap { Int($0) }
    }
    static func < (left: Self, right: Self) -> Bool { left.parts.lexicographicallyPrecedes(right.parts) }
    static func == (left: Self, right: Self) -> Bool { left.parts == right.parts }
}

struct MacRelease: Codable, Equatable {
    let version: String
    let releaseURL: URL
    let downloadURL: URL
}

struct UpdateRepository {
    let name: String
    init?(_ name: String) {
        let parts = name.split(separator: "/", omittingEmptySubsequences: false)
        guard parts.count == 2, parts.allSatisfy({
            $0 != "." && $0 != ".." && $0.range(of: "\\A[A-Za-z0-9_.-]{1,100}\\z", options: .regularExpression) != nil
        }) else { return nil }
        self.name = name
    }
    var apiURL: URL { URL(string: "https://api.github.com/repos/\(name)/releases?per_page=100")! }
    func accepts(_ release: MacRelease) -> Bool {
        guard MacVersion(release.version) != nil else { return false }
        return acceptsURL(release.releaseURL, prefix: "/\(name)/releases/tag/")
            && acceptsURL(release.downloadURL, prefix: "/\(name)/releases/download/")
            && release.downloadURL.lastPathComponent == "kjbk-projekt-guru-mac-\(release.version).zip"
    }
    private func acceptsURL(_ url: URL, prefix: String) -> Bool {
        url.scheme == "https" && url.host == "github.com" && (url.port == nil || url.port == 443)
            && url.user == nil && url.password == nil && url.query == nil && url.fragment == nil
            && url.path.lowercased().hasPrefix(prefix.lowercased()) && url.path.count > prefix.count
            && !url.path.split(separator: "/").contains(where: { $0 == "." || $0 == ".." })
    }
    func newest(in data: Data) throws -> MacRelease? {
        let releases = try JSONDecoder().decode([PublishedRelease].self, from: data)
        return releases.filter { !$0.draft && !$0.prerelease }.flatMap { release in
            release.assets.compactMap { asset -> MacRelease? in
                let prefix = "kjbk-projekt-guru-mac-", suffix = ".zip"
                guard asset.state == "uploaded", asset.name.hasPrefix(prefix), asset.name.hasSuffix(suffix) else { return nil }
                let version = String(asset.name.dropFirst(prefix.count).dropLast(suffix.count))
                let candidate = MacRelease(version: version, releaseURL: release.html_url, downloadURL: asset.browser_download_url)
                return accepts(candidate) ? candidate : nil
            }
        }.max { MacVersion($0.version)! < MacVersion($1.version)! }
    }
    private struct PublishedRelease: Decodable {
        let draft: Bool
        let prerelease: Bool
        let html_url: URL
        let assets: [Asset]
    }
    private struct Asset: Decodable {
        let name: String
        let state: String
        let browser_download_url: URL
    }
}
