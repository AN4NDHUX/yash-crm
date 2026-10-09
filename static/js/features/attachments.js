// Attachment-specific form and storage integration. Keep core route controller small.
export function installAttachmentPicker(root) {
  root.insertAdjacentHTML("afterbegin", '<div class="field full" style="margin-bottom:16px"><label for="attachment-upload-file">Upload file *</label><input class="field-input" id="attachment-upload-file" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg" required /><small>Maximum 10 MB</small></div>');
  root.querySelector("#attachment-upload-file").addEventListener("change", event => {
    const file = event.target.files?.[0];
    if (!file) return;
    for (const [key, value] of Object.entries({
      name: file.name, file_type: file.type || "File", file_size: String(file.size)
    })) {
      const input = root.querySelector('[name="' + key + '"]');
      if (input) input.value = value;
    }
  });
}

export async function createAttachmentFromFile(form, data, api) {
  const upload = form.querySelector("#attachment-upload-file")?.files?.[0];
  if (!upload) throw new Error("Select a file to upload.");
  if (upload.size > 10000000) throw new Error("Maximum attachment size is 10 MB.");
  const body = new FormData();
  body.append("file", upload);
  body.append("name", String(data.name || upload.name));
  if (data.related_type) body.append("related_type", data.related_type);
  if (data.related_id) body.append("related_id", String(data.related_id));
  const response = await fetch("/api/documents/upload", {
    method: "POST", body, credentials: "same-origin"
  });
  const raw = await response.text();
  let doc = {};
  try { doc = JSON.parse(raw); } catch { /* response handled below */ }
  if (!response.ok) throw new Error(doc.detail || "Upload failed (" + response.status + ")");
  const attachment = {
    ...data,
    name: String(data.name || upload.name),
    file_type: String(data.file_type || upload.type || "File").slice(0, 80),
    file_size: String(upload.size),
    url: "/api/documents/" + doc.id + "/download",
  };
  await api("/api/attachments", { method: "POST", body: JSON.stringify(attachment) });
}
