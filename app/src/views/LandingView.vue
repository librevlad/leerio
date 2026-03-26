<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { isLoggedIn, checkAuth } = useAuth()

onMounted(async () => {
  await checkAuth()
  if (isLoggedIn.value) {
    router.replace('/library')
  }
})

function scrollToFeatures() {
  document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<template>
  <div class="landing">
    <!-- Hero -->
    <section class="hero">
      <!-- Ambient glow -->
      <div class="hero-glow" />

      <div class="hero-inner">
        <img src="/logo.png" alt="Leerio" class="hero-logo" />
        <h1 class="hero-title font-display">
          Your audiobooks.<br />
          Every device. No server.
        </h1>
        <p class="hero-subtitle">
          Upload your audiobook files and listen anywhere — phone, tablet, laptop. Your position syncs automatically.
        </p>
        <div class="hero-actions">
          <router-link to="/library" class="btn btn-primary hero-cta">Try Free</router-link>
          <button class="btn btn-ghost hero-cta-secondary" @click="scrollToFeatures">Learn More</button>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section id="features" class="features">
      <div class="features-inner">
        <div class="feature-card card">
          <div class="feature-icon">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <h3 class="feature-title">Upload</h3>
          <p class="feature-desc">Drag & drop your audiobook files. MP3, M4A, M4B, ZIP supported.</p>
        </div>

        <div class="feature-card card">
          <div class="feature-icon">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
              <path
                d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"
              />
            </svg>
          </div>
          <h3 class="feature-title">Listen anywhere</h3>
          <p class="feature-desc">Phone, tablet, laptop. Pick up exactly where you left off.</p>
        </div>

        <div class="feature-card card">
          <div class="feature-icon">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h3 class="feature-title">No server needed</h3>
          <p class="feature-desc">No Docker, no NAS, no setup. Just upload and listen.</p>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="landing-footer">
      <div class="footer-inner">
        <div class="footer-links">
          <router-link to="/login" class="footer-link">Sign in</router-link>
          <span class="footer-sep"></span>
          <a href="/legal/dmca" class="footer-link">DMCA</a>
        </div>
        <p class="footer-brand">Made by Leerio</p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--bg);
  color: var(--t1);
  overflow-x: hidden;
}

/* ── Hero ──────────────────────────────────────────────────────────────── */

.hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  min-height: 100dvh;
  padding: 64px 16px;
}

.hero-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 70% 50% at 50% 30%, rgba(255, 138, 0, 0.07) 0%, transparent 70%);
  pointer-events: none;
}

.hero-inner {
  position: relative;
  max-width: 640px;
  text-align: center;
}

.hero-logo {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  margin-bottom: 32px;
}

.hero-title {
  font-size: 36px;
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--t1);
  margin: 0 0 20px;
}

.hero-subtitle {
  font-size: 16px;
  line-height: 1.6;
  color: var(--t2);
  margin: 0 auto 40px;
  max-width: 480px;
}

.hero-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.hero-cta {
  text-decoration: none;
  font-size: 15px;
  padding: 14px 32px;
  min-height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.hero-cta-secondary {
  font-size: 15px;
  padding: 14px 32px;
  min-height: 48px;
}

/* ── Features ──────────────────────────────────────────────────────────── */

.features {
  padding: 80px 16px;
}

.features-inner {
  max-width: 960px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.feature-card {
  padding: 32px 24px;
  text-align: center;
}

.feature-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.feature-title {
  font-family: 'Satoshi', 'DM Sans', system-ui, sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--t1);
  margin: 0 0 8px;
}

.feature-desc {
  font-size: 14px;
  line-height: 1.5;
  color: var(--t2);
  margin: 0;
}

/* ── Footer ────────────────────────────────────────────────────────────── */

.landing-footer {
  border-top: 1px solid var(--border);
  padding: 32px 16px;
}

.footer-inner {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.footer-links {
  display: flex;
  align-items: center;
  gap: 16px;
}

.footer-link {
  font-size: 13px;
  color: var(--t3);
  text-decoration: none;
  transition: color 0.15s ease;
}

.footer-link:hover {
  color: var(--t2);
}

.footer-sep {
  width: 1px;
  height: 14px;
  background: var(--border);
}

.footer-brand {
  font-size: 12px;
  color: var(--t3);
  margin: 0;
}

/* ── Responsive ────────────────────────────────────────────────────────── */

@media (min-width: 640px) {
  .hero-title {
    font-size: 48px;
  }

  .hero-subtitle {
    font-size: 17px;
  }

  .features {
    padding: 96px 24px;
  }

  .features-inner {
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }

  .feature-card {
    padding: 36px 28px;
  }

  .landing-footer {
    padding: 40px 24px;
  }
}
</style>
