import CryptoKit
import Darwin
import Foundation
import ImageIO
import Vision

struct OCRResult: Codable {
    let status: String
    let text: String?
    let extractor_name: String
    let extractor_version: String
    let confidence: Double?
    let caveat: String?
    let claim_status: String
    let audit_status: String
    let reviewer: String?
    let error: String?
}

func emit(_ result: OCRResult) {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let data = try! encoder.encode(result)
    print(String(data: data, encoding: .utf8)!)
}

func helperVersion() -> String {
    let executable = URL(fileURLWithPath: CommandLine.arguments[0])
    let helperHash: String
    if let data = try? Data(contentsOf: executable) {
        helperHash = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    } else {
        helperHash = "unavailable"
    }
    return "Vision.VNRecognizeTextRequest; \(ProcessInfo.processInfo.operatingSystemVersionString); helper-sha256:\(helperHash)"
}

func failure(_ message: String) {
    emit(
        OCRResult(
            status: "failed",
            text: nil,
            extractor_name: "apple-vision-vnrecognizetextrequest",
            extractor_version: helperVersion(),
            confidence: nil,
            caveat: "local Apple Vision OCR; no network access",
            claim_status: "unknown",
            audit_status: "needs_reconciliation",
            reviewer: nil,
            error: message
        )
    )
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard let inputIndex = arguments.firstIndex(of: "--input"), inputIndex + 1 < arguments.count else {
    failure("usage: serenity_vision_ocr --input <image-path>")
    exit(2)
}

let imageURL = URL(fileURLWithPath: arguments[inputIndex + 1])
guard let source = CGImageSourceCreateWithURL(imageURL as CFURL, nil), let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    failure("unable to decode image at \(imageURL.path)")
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
if #available(macOS 13.0, *) {
    request.automaticallyDetectsLanguage = true
}

do {
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])
    let observations = request.results ?? []
    let lines = observations.compactMap { $0.topCandidates(1).first?.string }
    let confidence = observations.compactMap { $0.topCandidates(1).first?.confidence }.map(Double.init).max()
    let text = lines.joined(separator: "\n")
    emit(
        OCRResult(
            status: "complete",
            text: text,
            extractor_name: "apple-vision-vnrecognizetextrequest",
            extractor_version: helperVersion(),
            confidence: confidence,
            caveat: "local Apple Vision OCR; text presence does not establish an investment claim",
            claim_status: "insufficient",
            audit_status: "unreviewed",
            reviewer: nil,
            error: nil
        )
    )
} catch {
    failure("Vision OCR failed: \(error.localizedDescription)")
    exit(4)
}
