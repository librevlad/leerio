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

    <!-- How it works -->
    <section id="features" class="how-it-works">
      <div class="how-inner">
        <h2 class="how-heading font-display">How it works</h2>
        <div class="steps">
          <div class="step">
            <span class="step-num font-display">01</span>
            <div class="step-content">
              <h3 class="step-title">Upload your files</h3>
              <p class="step-desc">Drag & drop MP3, M4A, M4B, or ZIP. No metadata forms, no setup.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-num font-display">02</span>
            <div class="step-content">
              <h3 class="step-title">Listen anywhere</h3>
              <p class="step-desc">Phone, tablet, laptop. Open Leerio and your book is right where you left off.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-num font-display">03</span>
            <div class="step-content">
              <h3 class="step-title">No server needed</h3>
              <p class="step-desc">No Docker, no NAS, no self-hosting. We handle the infrastructure.</p>
            </div>
          </div>
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

/* ── How it works ─────────────────────────────────────────────────────── */

.how-it-works {
  padding: 80px 16px;
  border-top: 1px solid var(--border);
}

.how-inner {
  max-width: 640px;
  margin: 0 auto;
}

.how-heading {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--t3);
  margin: 0 0 48px;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.step {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.step-num {
  font-size: 32px;
  font-weight: 900;
  color: var(--accent);
  line-height: 1;
  flex-shrink: 0;
  width: 52px;
  opacity: 0.8;
}

.step-content {
  flex: 1;
  padding-top: 4px;
}

.step-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--t1);
  margin: 0 0 6px;
}

.step-desc {
  font-size: 14px;
  line-height: 1.6;
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

  .how-it-works {
    padding: 96px 24px;
  }

  .step-num {
    font-size: 40px;
    width: 64px;
  }

  .step-title {
    font-size: 18px;
  }

  .landing-footer {
    padding: 40px 24px;
  }
}
</style>
