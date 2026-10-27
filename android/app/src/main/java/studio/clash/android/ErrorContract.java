package studio.clash.android;
import org.json.JSONObject;
final class ErrorContract {
    static String code(int status) {
        switch (status) {
            case 400: case 422: return "INVALID_REQUEST";
            case 403: return "FORBIDDEN";
            case 404: return "NOT_FOUND";
            case 409: return "CONFLICT";
            case 413: return "LIMIT_EXCEEDED";
            case 428: return "PERMISSION_REQUIRED";
            case 429: return "BUSY";
            case 501: return "UNSUPPORTED";
            case 502: return "CORE_UNCONFIRMED";
            case 503: return "UNAVAILABLE";
            case 504: return "TIMEOUT";
            default: return "INTERNAL_ERROR";
        }
    }
    static JSONObject error(int status, String code, String message) throws Exception {
        return new JSONObject().put("code", code).put("message", message).put("retryable", status == 409 || status == 429 || status >= 500).put("operation_id", JSONObject.NULL);
    }
}
