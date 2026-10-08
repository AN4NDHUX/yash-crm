export async function requestJson(path, options = {}, csrfToken = null) {
  let response;
  const { headers: extraHeaders, ...fetchOptions } = options;
  try {
    response = await fetch(path, {
      credentials: "same-origin",
      ...fetchOptions,
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-Yash-CSRF": csrfToken } : {}),
        ...(extraHeaders || {}),
      },
    });
  } catch {
    const error = new Error("CONVOSIS CRM could not reach the server. Check the connection and try again.");
    error.code = "NETWORK_ERROR";
    throw error;
  }

  const raw = await response.text();
  let body = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    body = {};
  }

  if (!response.ok) {
    const detail = body.detail && typeof body.detail === "object" ? body.detail : null;
    const message = response.status === 401
      ? "You are not signed in, or your sign-in expired. Reload the page and enter your credentials again."
      : (detail?.message || body.detail || body.message || raw.slice(0, 180) || `Request failed with HTTP ${response.status}`);
    const error = new Error(message);
    error.status = response.status;
    error.code = detail?.code || body.code || null;
    error.body = body;
    throw error;
  }

  return body;
}
