import json, requests
from xblock.core import XBlock
from xblock.fields import Scope, String, Boolean
from xblock.fragment import Fragment

DEFAULT_API_BASE = "https://your-fastapi.example.org"  # change or override in Studio

class HelloPdfSubmissionXBlock(XBlock):
    """
    Minimal XBlock: learner types text -> we POST to FastAPI -> store returned link as submission.
    """
    # 👇 these make it show up in Studio's palette
    category = "hello-pdf-submission"      # must match the slug you added in Advanced Module List
    display_name = "Hello Pdf Submission"  # the label you’ll see in Studio
    icon_class = "problem"                  # or "other", "video", etc. purely visual
    
    # Author-configurable
    api_base = String(default=DEFAULT_API_BASE, scope=Scope.content, help="FastAPI base URL")
    title = String(default="My Assignment", scope=Scope.content)

    # Per-learner state
    submitted = Boolean(default=False, scope=Scope.user_state)
    artifact_url = String(default="", scope=Scope.user_state)

    # ---------- Student view ----------
    def student_view(self, context=None):
        if not self.submitted:
            html = f"""
<div class="hpdf">
  <label>Title</label>
  <input id="hpdf-title" value="{self.title}" style="width:100%;margin-bottom:8px;" />
  <label>Your Text</label>
  <textarea id="hpdf-text" rows="8" style="width:100%;"></textarea>
  <button id="hpdf-submit" style="margin-top:8px;">Check & Submit</button>
  <div id="hpdf-msg" style="margin-top:8px;color:#555;"></div>
</div>
"""
        else:
            html = f"""
<div class="hpdf">
  <p><strong>Submitted.</strong></p>
  <p>Artifact: <a id="hpdf-link" href="{self.artifact_url}" target="_blank">{self.artifact_url}</a></p>
  <button id="hpdf-resubmit">Resubmit</button>
</div>
"""

        js = """
function HelloPdfInit(runtime, element) {
  function call(handler, payload) {
    return $.ajax({
      type: "POST",
      url: runtime.handlerUrl(element, handler),
      data: JSON.stringify(payload || {}),
      contentType: "application/json"
    });
  }

  const submitBtn = element.querySelector('#hpdf-submit');
  const resubmitBtn = element.querySelector('#hpdf-resubmit');
  const msg = element.querySelector('#hpdf-msg');

  if (submitBtn) {
    submitBtn.addEventListener('click', () => {
      const title = element.querySelector('#hpdf-title').value || 'Assignment';
      const text = element.querySelector('#hpdf-text').value || '';
      if (msg) msg.textContent = 'Submitting...';
      call('submit_text', {title, text}).then(resp => {
        if (msg) msg.textContent = resp.message || 'Submitted';
        if (resp.reload) window.location.reload();
      }).fail(err => {
        if (msg) msg.textContent = 'Error: ' + (err.responseText || err.statusText);
      });
    });
  }
  if (resubmitBtn) {
    resubmitBtn.addEventListener('click', () => {
      call('reset_submission', {}).then(() => window.location.reload());
    });
  }
}
"""
        frag = Fragment(html)
        frag.add_javascript(js)
        frag.initialize_js('HelloPdfInit')
        return frag

    # ---------- Simple authoring view (set API base) ----------
    def studio_view(self, context=None):
        html = f"""
<div class="hpdf-studio">
  <p>FastAPI Base URL:</p>
  <input id="api-base" value="{self.api_base}" style="width:100%;" />
  <p style="margin-top:8px;">Title (default for students):</p>
  <input id="title" value="{self.title}" style="width:100%;" />
  <button id="save">Save</button>
  <div id="msg" style="margin-top:8px;color:#555;"></div>
</div>
"""
        js = """
function HelloPdfStudioInit(runtime, element) {
  const saveBtn = element.querySelector('#save');
  const msg = element.querySelector('#msg');
  saveBtn.addEventListener('click', () => {
    const api_base = element.querySelector('#api-base').value;
    const title = element.querySelector('#title').value;
    $.ajax({
      type: "POST",
      url: runtime.handlerUrl(element, 'studio_submit'),
      data: JSON.stringify({api_base, title}),
      contentType: "application/json"
    }).then(() => { if (msg) msg.textContent = 'Saved.'; })
      .fail(err => { if (msg) msg.textContent = 'Error: ' + (err.responseText || err.statusText); });
  });
}
"""
        frag = Fragment(html)
        frag.add_javascript(js)
        frag.initialize_js('HelloPdfStudioInit')
        return frag

    # ---------- Handlers ----------
    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        self.api_base = (data or {}).get('api_base') or self.api_base
        self.title = (data or {}).get('title') or self.title
        return {"ok": True}

    @XBlock.json_handler
    def reset_submission(self, data, suffix=''):
        self.submitted = False
        self.artifact_url = ""
        # Optional: ungrade
        # self.runtime.publish(self, 'grade', {'value': 0, 'max_value': 1})
        return {"ok": True}

    @XBlock.json_handler
    def submit_text(self, data, suffix=''):
        # Gather context for your FastAPI
        user_id = str(self.runtime.user_id)
        course_id = str(self.runtime.course_id)
        unit_id = str(self.location)

        title = (data or {}).get('title') or self.title
        text = (data or {}).get('text') or ''

        payload = {"text": text, "title": title, "learner_id": user_id,
                   "course_id": course_id, "unit_id": unit_id}
        try:
            r = requests.post(self.api_base.rstrip('/') + "/render/text", json=payload, timeout=30)
            r.raise_for_status()
            res = r.json()
        except Exception as e:
            return {"ok": False, "message": f"Service error: {e}"}

        url = res.get("download_url") or ""
        if not url:
            return {"ok": False, "message": "Service did not return download_url"}

        self.artifact_url = url
        self.submitted = True

        # Optional: mark complete (1/1). Remove if you want staff/peer grading elsewhere.
        try:
            self.runtime.publish(self, 'grade', {'value': 1, 'max_value': 1})
        except Exception:
            pass

        return {"ok": True, "message": "Submitted successfully.", "reload": True}
