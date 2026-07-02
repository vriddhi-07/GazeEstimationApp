(() => {
  const captureStatus = document.getElementById("captureStatus");
  const participantId = document.body?.dataset?.participantId || "";

  // Helper: read a cookie by name
  const getCookie = (name) => {
    const match = document.cookie
      .split(";")
      .map((c) => c.trim())
      .find((c) => c.startsWith(name + "="));
    return match ? match.split("=")[1] : "";
  };

  // Always read the CSRF token fresh (capture_session_view uses @ensure_csrf_cookie)
  const getCsrfToken = () => getCookie("csrftoken");

  const sessionStamp = Date.now();
  const activeRecorders = [];
  const pendingUploads = new Set();
  const pendingFinalizations = [];
  let stoppedAll = false;
  const controlChannel =
    "BroadcastChannel" in window
      ? new BroadcastChannel("survey-capture-control")
      : null;
  let openerWatchTimer = null;
  let openerClosedChecks = 0;
  let heartbeatWatchTimer = null;
  let lastHeartbeatAt = Date.now();
  const activeStreams = [];

  const setStatus = (message, isError = false) => {
    if (!captureStatus) return;
    captureStatus.textContent = message;
    captureStatus.style.color = isError ? "#b42318" : "#0e7a58";
  };

  const uploadClipChunk = async (blob, endpoint, filenamePrefix) => {
    const formData = new FormData();
    formData.append("clip", blob, `${filenamePrefix}-${sessionStamp}.webm`);
    formData.append("session_stamp", String(sessionStamp));
    formData.append("participant_id", participantId);
    formData.append("csrfmiddlewaretoken", getCsrfToken());

    const uploadPromise = fetch(endpoint, {
      method: "POST",
      body: formData,
      headers: { "X-CSRFToken": getCsrfToken() },
    })
      .catch((err) => {
        console.error(`Failed to upload clip chunk to ${endpoint}`, err);
      })
      .finally(() => {
        pendingUploads.delete(uploadPromise);
      });

    pendingUploads.add(uploadPromise);
    await uploadPromise;
  };

  // FIX: Use fetch() for finalize instead of sendBeacon().
  // sendBeacon() cannot send custom headers, so the CSRF token is lost and
  // Django rejects the request with 403 Forbidden.  fetch() with keepalive:true
  // behaves similarly (survives page unload) but correctly carries the header.
  const finalizeClip = async (endpoint, startedAt, endedAt) => {
    if (pendingUploads.size > 0) {
      await Promise.allSettled(Array.from(pendingUploads));
    }

    const formData = new FormData();
    formData.append("session_stamp", String(sessionStamp));
    formData.append("participant_id", participantId);
    formData.append("csrfmiddlewaretoken", getCsrfToken());
    if (startedAt) formData.append("started_at", String(startedAt));
    if (endedAt) formData.append("ended_at", String(endedAt));

    await fetch(endpoint, {
      method: "POST",
      body: formData,
      headers: { "X-CSRFToken": getCsrfToken() },
      keepalive: true,
    }).catch(() => {
      console.warn(`Could not finalize recording at ${endpoint}`);
    });
  };

  const startRecorder = (stream, endpoint, finalizeEndpoint, filenamePrefix) => {
    if (typeof MediaRecorder === "undefined") return null;

    let recorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
    } catch (err) {
      try {
        recorder = new MediaRecorder(stream);
      } catch (innerErr) {
        console.error(
          `Could not start MediaRecorder for ${endpoint}`,
          innerErr
        );
        return null;
      }
    }

    // Chunks must land on disk in the exact order MediaRecorder produced
    // them, or the reassembled .webm has scrambled timestamps (the server
    // just does destination.write() per request, so two in-flight uploads
    // racing each other can append out of order). ondataavailable fires on
    // a timer regardless of whether the previous chunk's upload finished,
    // so we chain each upload off the previous one's promise instead of
    // firing them independently — this recorder's chunks are always sent
    // one-at-a-time, in order, and the next chunk's request isn't even
    // opened until the last one is confirmed written server-side.
    let uploadQueue = Promise.resolve();

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        const data = event.data;
        uploadQueue = uploadQueue.then(() =>
          uploadClipChunk(data, endpoint, filenamePrefix)
        );
      }
    };
    let startedAt = null;
    recorder.onstop = () => {
      const endedAt = Date.now();
      // Wait for every chunk we've queued (including one that may have just
      // been queued by a final requestData() and hasn't started uploading
      // yet) to actually land on disk before telling the server to convert —
      // otherwise finalize can race ahead of the last chunk's upload.
      const finalizePromise = uploadQueue
        .catch(() => {})
        .then(() => finalizeClip(finalizeEndpoint, startedAt, endedAt))
        .finally(() => {
          const idx = pendingFinalizations.indexOf(finalizePromise);
          if (idx >= 0) pendingFinalizations.splice(idx, 1);
        });
      pendingFinalizations.push(finalizePromise);
    };
    startedAt = Date.now();
    recorder.start(3000);
    activeRecorders.push(recorder);
    activeStreams.push(stream);
    return recorder;
  };

  const stopAllRecorders = async () => {
    if (stoppedAll) return;
    stoppedAll = true;

    activeRecorders.forEach((recorder) => {
      if (recorder && recorder.state !== "inactive") {
        try { recorder.requestData(); } catch (e) {}
        recorder.stop();
      }
    });
    activeStreams.forEach((stream) => {
      stream.getTracks().forEach((track) => {
        try { track.stop(); } catch (e) {}
      });
    });

    await new Promise((resolve) => window.setTimeout(resolve, 250));
    if (pendingFinalizations.length > 0) {
      await Promise.allSettled([...pendingFinalizations]);
    }
  };

const handleStopMessage = async (payload) => {
  if (payload?.type === "stop-capture-session") {
    setStatus("Finalizing recordings…");

    await stopAllRecorders();

    console.log("Finished stopAllRecorders()");

    if (openerWatchTimer) {
      window.clearInterval(openerWatchTimer);
    }

    console.log("Waiting 30 seconds before closing popup...");

    setTimeout(() => {
      console.log("Closing popup");
      window.close();
    }, 40000);   // 30 seconds
  }
};

  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin) return;
    void handleStopMessage(event.data);
  });

  if (controlChannel) {
    controlChannel.addEventListener("message", (event) => {
      if (event.data?.type === "survey-heartbeat") {
        lastHeartbeatAt = Date.now();
        return;
      }
      void handleStopMessage(event.data);
    });
  }

  window.addEventListener("beforeunload", () => void stopAllRecorders());
  window.addEventListener("pagehide", () => void stopAllRecorders());

  if (window.opener) {
    openerWatchTimer = window.setInterval(() => {
      if (window.opener.closed) {
        openerClosedChecks += 1;
      } else {
        openerClosedChecks = 0;
      }
      if (openerClosedChecks >= 5) {
        stopAllRecorders();
        window.close();
      }
    }, 1000);
  }

  if (controlChannel) {
    heartbeatWatchTimer = window.setInterval(() => {
      if (Date.now() - lastHeartbeatAt < 60000) return;
      void stopAllRecorders().finally(() => {
        if (openerWatchTimer) window.clearInterval(openerWatchTimer);
        if (heartbeatWatchTimer) window.clearInterval(heartbeatWatchTimer);
        window.close();
      });
    }, 1000);
  }

  const normalizeError = (err) => {
    if (!err) return "unknown-error";
    return err.name || err.message || String(err);
  };

  const getPreferredWebcamConstraints = async () => {
    const fallback = { width: { ideal: 1280 }, height: { ideal: 720 } };
    if (!navigator.mediaDevices?.enumerateDevices) return fallback;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoInputs = devices.filter((d) => d.kind === "videoinput");
      if (videoInputs.length === 0) return fallback;
      const preferred =
        videoInputs.find((d) =>
          /external|usb|logi|webcam|camera/i.test(d.label)
        ) || videoInputs[0];
      const constraints = { width: { ideal: 1280 }, height: { ideal: 720 } };
      if (preferred.deviceId) constraints.deviceId = { ideal: preferred.deviceId };
      return constraints;
    } catch (err) {
      console.warn("Could not enumerate video devices", err);
      return fallback;
    }
  };

  const startCaptureSession = async () => {
    console.log("Starting capture");
    if (!window.isSecureContext) {
      setStatus(
        "Recording is unavailable on this address. Open the survey on localhost or HTTPS to allow screen and webcam access.",
        true
      );
      return;
    }

    if (
      !navigator.mediaDevices?.getDisplayMedia ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      setStatus(
        "This browser does not support the required media APIs. Use a current browser on localhost or HTTPS.",
        true
      );
      return;
    }

    // FIX: Attempt both streams independently.  The original code aborted if
    // either permission was denied, meaning a user who only denied screen-share
    // would lose the webcam recording entirely.  Now each stream is attempted
    // separately; we proceed with whatever succeeds, and report partial failures.
    let screenStream = null;
    let webcamStream = null;
    const errors = [];

    try {
      setStatus("Requesting screen-sharing access…");
      screenStream = await navigator.mediaDevices.getDisplayMedia({
        
        video: {
          displaySurface: "monitor",
          selfBrowserSurface: "exclude",
          surfaceSwitching: "exclude",
          monitorTypeSurfaces: "include",
          preferCurrentTab: false,
          frameRate: { ideal: 15, max: 30 },
        },
        audio: false,
      });
    } catch (err) {
      errors.push(`screen: ${normalizeError(err)}`);
      console.warn("Screen capture was not started", err);
    }

    try {
      setStatus(
        screenStream
          ? "Screen sharing approved. Requesting webcam access…"
          : "Requesting webcam access…"
      );
      const webcamConstraints = await getPreferredWebcamConstraints();
      webcamStream = await navigator.mediaDevices.getUserMedia({
        video: webcamConstraints,
        audio: false,
      });
    } catch (err) {
      errors.push(`webcam: ${normalizeError(err)}`);
      console.warn("Webcam capture was not started", err);
    }

    // Require at least the webcam stream — that is the gaze-estimation input.
    if (!webcamStream) {
      [screenStream].filter(Boolean).forEach((s) =>
        s.getTracks().forEach((t) => { try { t.stop(); } catch (e) {} })
      );
      setStatus(
        "Webcam access is required for this study. Please allow webcam access and reload the capture window.",
        true
      );
      if (errors.length > 0) console.error("Capture session failed:", errors.join("; "));
      return;
    }

    // Start webcam recorder (always present).
    const webcamRecorder = startRecorder(
      webcamStream,
      "/api/webcam/upload/",
      "/api/webcam/finalize/",
      "webcam-clip"
    );

    if (!webcamRecorder) {
      stopAllRecorders();
      setStatus("Could not initialise the webcam recorder. Try a different browser.", true);
      return;
    }

    // Start screen recorder if permission was granted.
    let screenRecorder = null;
    if (screenStream) {
      screenRecorder = startRecorder(
        screenStream,
        "/api/screen/upload/",
        "/api/screen/finalize/",
        "screen-clip"
      );
      if (!screenRecorder) {
        screenStream.getTracks().forEach((t) => { try { t.stop(); } catch (e) {} });
      }
    }

    // Stop both if either stream ends (e.g. user revokes screen share).
    const syncStop = () => stopAllRecorders();
    if (screenStream) {
      screenStream.getVideoTracks().forEach((t) =>
        t.addEventListener("ended", syncStop)
      );
    }
    webcamStream.getVideoTracks().forEach((t) =>
      t.addEventListener("ended", syncStop)
    );

    if (screenRecorder) {
      setStatus(
        `Recording is active for this survey session (screen + webcam, session ${sessionStamp}).`
      );
    } else {
      setStatus(
        `Webcam recording is active (screen sharing was not granted, session ${sessionStamp}).`
      );
    }
  };

  startCaptureSession();
})();