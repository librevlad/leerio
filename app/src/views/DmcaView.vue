<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="dmca-page">
    <button class="dmca-back" @click="router.back()">&larr; Back</button>
    <h1 class="dmca-title">DMCA Policy</h1>
    <p class="dmca-date">Last updated: March 26, 2026</p>

    <section>
      <h2 class="dmca-heading">Notification of Copyright Infringement</h2>
      <p class="dmca-text">
        Leerio respects intellectual property rights. If you believe content hosted on Leerio infringes your copyright,
        please send a written notification containing:
      </p>
      <ul class="dmca-list">
        <li>Your physical or electronic signature</li>
        <li>Identification of the copyrighted work claimed to be infringed</li>
        <li>Identification of the material that is claimed to be infringing, with enough detail to locate it</li>
        <li>Your contact information (address, telephone number, email)</li>
        <li>
          A statement that you have a good faith belief that the use is not authorized by the copyright owner, its
          agent, or the law
        </li>
        <li>
          A statement, made under penalty of perjury, that the information in the notification is accurate and that you
          are authorized to act on behalf of the copyright owner
        </li>
      </ul>
    </section>

    <section>
      <h2 class="dmca-heading">DMCA Agent</h2>
      <p class="dmca-text">
        Send copyright infringement notifications to:
        <a href="mailto:dmca@leerio.app" class="dmca-link">dmca@leerio.app</a>
      </p>
      <p class="dmca-text">Please include "DMCA Notice" in the subject line.</p>
    </section>

    <section>
      <h2 class="dmca-heading">Counter-Notification</h2>
      <p class="dmca-text">
        If you believe your content was removed in error, you may send a counter-notification containing:
      </p>
      <ul class="dmca-list">
        <li>Your physical or electronic signature</li>
        <li>Identification of the material that was removed and the location where it previously appeared</li>
        <li>
          A statement under penalty of perjury that you believe the material was removed or disabled as a result of
          mistake or misidentification
        </li>
        <li>Your name, address, and telephone number</li>
        <li>
          A statement that you consent to the jurisdiction of the federal district court for the judicial district in
          which your address is located, and that you will accept service of process from the person who provided the
          original DMCA notification
        </li>
      </ul>
    </section>

    <section>
      <h2 class="dmca-heading">Repeat Infringers</h2>
      <p class="dmca-text">
        Leerio will, in appropriate circumstances, terminate the accounts of users who are repeat infringers of
        copyrighted works.
      </p>
    </section>
  </div>
</template>

<style scoped>
.dmca-page {
  max-width: 800px;
  margin: 0 auto;
}

.dmca-back {
  display: inline-block;
  margin-bottom: 24px;
  padding: 0;
  border: none;
  background: none;
  color: var(--t3);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.15s;
}

.dmca-back:hover {
  color: var(--t1);
}

.dmca-title {
  font-size: 24px;
  font-weight: 800;
  color: var(--t1);
  margin-bottom: 4px;
}

.dmca-date {
  font-size: 13px;
  color: var(--t3);
  margin-bottom: 32px;
}

.dmca-heading {
  font-size: 18px;
  font-weight: 700;
  color: var(--t1);
  margin: 28px 0 10px;
}

.dmca-text {
  font-size: 14px;
  color: var(--t2);
  line-height: 1.7;
  margin-bottom: 12px;
}

.dmca-list {
  padding-left: 20px;
  margin-bottom: 12px;
}

.dmca-list li {
  font-size: 14px;
  color: var(--t2);
  line-height: 1.7;
  margin-bottom: 6px;
}

.dmca-link {
  color: var(--accent);
  text-decoration: none;
}

.dmca-link:hover {
  text-decoration: underline;
}
</style>
