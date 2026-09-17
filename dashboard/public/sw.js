/* WordLock PWA service worker — offline shell + Web Push notifications */

const CACHE = "wordlock-v2";
const DB_NAME = "wordlock-sw";
const DB_VERSION = 1;
const STORE = "meta";

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbGet(key) {
  return openDb().then(
    (db) =>
      new Promise((resolve) => {
        const tx = db.transaction(STORE, "readonly");
        const get = tx.objectStore(STORE).get(key);
        get.onsuccess = () => resolve(get.result);
        get.onerror = () => resolve(null);
      })
  );
}

function idbSet(key, value) {
  return openDb().then(
    (db) =>
      new Promise((resolve) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).put(value, key);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      })
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(["/", "/manifest.webmanifest", "/icon-192.png"]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  if (!event.request.url.startsWith(self.location.origin)) return;
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      });
    })
  );
});

async function isMutedDown(downId) {
  if (!downId) return false;
  const muted = await idbGet("mutedDownId");
  return muted === String(downId);
}

async function muteDown(downId) {
  if (downId) await idbSet("mutedDownId", String(downId));
  try {
    await fetch("/api/admin/monitor/mute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ muted: true }),
    });
  } catch (e) {
    /* backend unreachable — local mute still applies */
  }
}

self.addEventListener("push", (event) => {
  let data = {
    title: "WordLock",
    body: "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    url: "/admin/incidents",
    tag: "wordlock-alert",
    actions: [],
    downId: null,
  };
  try {
    if (event.data) data = Object.assign(data, event.data.json());
  } catch (e) {
    /* ignore malformed payload */
  }
  event.waitUntil(
    isMutedDown(data.downId).then((muted) => {
      if (muted) return;
      const options = {
        body: data.body,
        icon: data.icon,
        badge: data.badge,
        tag: data.tag,
        renotify: true,
        data: { url: data.url, downId: data.downId },
        actions: data.actions,
      };
      return self.registration.showNotification(data.title, options);
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action === "mute") {
    const downId = event.notification.data && event.notification.data.downId;
    event.waitUntil(muteDown(downId));
    return;
  }
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if ("focus" in client) return client.focus();
        }
        return self.clients.openWindow(url);
      })
  );
});
