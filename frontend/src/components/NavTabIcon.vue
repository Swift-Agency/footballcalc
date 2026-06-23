<template>
  <!-- Inline SVGs (no v-html) for nav security -->
  <svg
    v-if="name === 'schedule'"
    width="21"
    height="22"
    viewBox="0 0 21 22"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="nav-tab-svg"
    aria-hidden="true"
  >
    <path
      d="M16.3 0.799988V2.79999M4.30005 0.799988V2.79999M1.30005 6.79999H19.3M0.800049 11.043C0.800049 6.68599 0.800049 4.50699 2.05205 3.15299C3.30405 1.79999 5.32005 1.79999 9.35005 1.79999H11.25C15.28 1.79999 17.296 1.79999 18.548 3.15399C19.8 4.50699 19.8 6.68599 19.8 11.044V11.557C19.8 15.914 19.8 18.093 18.548 19.447C17.296 20.8 15.28 20.8 11.25 20.8H9.35005C5.32005 20.8 3.30405 20.8 2.05205 19.446C0.800049 18.093 0.800049 15.914 0.800049 11.556V11.043Z"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <svg
    v-else-if="name === 'leagues'"
    width="21"
    height="21"
    viewBox="0 0 21 21"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="nav-tab-svg"
    aria-hidden="true"
  >
    <path
      d="M12.7442 6.29999H4.30005M7.46647 11.3H4.2998M19.8 11.25V9.34999C19.8 5.31999 19.8 3.30399 18.409 2.05199C17.018 0.799988 14.779 0.799988 10.3 0.799988C5.82205 0.799988 3.58205 0.799988 2.19105 2.05199C0.800049 3.30399 0.800049 5.31999 0.800049 9.34999V11.25C0.800049 15.28 0.800049 17.296 2.19105 18.548C3.58205 19.8 5.82105 19.8 10.3 19.8C14.778 19.8 17.018 19.8 18.409 18.548C19.8 17.296 19.8 15.28 19.8 11.25Z"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <svg
    v-else-if="name === 'calculator'"
    width="21"
    height="21"
    viewBox="0 0 21 21"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="nav-tab-svg"
    aria-hidden="true"
  >
    <path
      d="M16.3 6.29999H12.3M14.3 4.29999V8.29999M16.3 15.8H12.3M16.3 12.8H12.3M8.30005 15.8L6.55005 14.05M6.55005 14.05L4.80005 12.3M6.55005 14.05L8.30005 12.3M6.55005 14.05L4.80005 15.8M8.30005 6.29999H4.30005M19.8 11.25V9.34999C19.8 5.31999 19.8 3.30399 18.409 2.05199C17.018 0.799988 14.779 0.799988 10.3 0.799988C5.82205 0.799988 3.58205 0.799988 2.19105 2.05199C0.800049 3.30399 0.800049 5.31999 0.800049 9.34999V11.25C0.800049 15.28 0.800049 17.296 2.19105 18.548C3.58205 19.8 5.82105 19.8 10.3 19.8C14.778 19.8 17.018 19.8 18.409 18.548C19.8 17.296 19.8 15.28 19.8 11.25Z"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <svg
    v-else-if="name === 'profile'"
    width="21"
    height="21"
    viewBox="0 0 21 21"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="nav-tab-svg"
    aria-hidden="true"
  >
    <path
      d="M10.3 0.799988C5.82205 0.799988 3.58205 0.799988 2.19105 2.05199C0.800049 3.30399 0.800049 5.31999 0.800049 9.34999V11.25C0.800049 15.28 0.800049 17.296 2.19105 18.548C3.58205 19.8 5.82105 19.8 10.3 19.8C14.778 19.8 17.018 19.8 18.409 18.548C19.8 17.296 19.8 15.28 19.8 11.25V9.34999C19.8 5.31999 19.8 3.30399 18.409 2.05199C17.018 0.799988 14.779 0.799988 10.3 0.799988Z"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      d="M6.80005 8.29999C6.80005 6.40399 8.40405 4.79999 10.3 4.79999C12.196 4.79999 13.8 6.40399 13.8 8.29999C13.8 10.196 12.196 11.8 10.3 11.8C8.40405 11.8 6.80005 10.196 6.80005 8.29999Z"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      d="M4.80005 16.8C5.64005 14.96 7.76005 13.8 10.3 13.8C12.84 13.8 14.96 14.96 15.8 16.8"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <svg
    v-else
    width="21"
    height="21"
    viewBox="0 0 21 21"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="nav-tab-svg"
    aria-hidden="true"
  >
    <path
      d="M10.3 14.4718V9.34999C10.3 8.86751 10.3 8.62576 10.1505 8.47518C9.99991 8.32562 9.75918 8.32562 9.27568 8.32562M10.044 5.25251H10.0532M19.8 11.25V9.34999C19.8 5.31999 19.8 3.30399 18.409 2.05199C17.018 0.799989 14.779 0.799988 10.3 0.799988C5.82205 0.799988 3.58205 0.799989 2.19105 2.05199C0.800049 3.30399 0.800049 5.31999 0.800049 9.34999V11.25C0.800049 15.28 0.800049 17.296 2.19105 18.548C3.58205 19.8 5.82105 19.8 10.3 19.8C14.778 19.8 17.018 19.8 18.409 18.548C19.8 17.296 19.8 15.28 19.8 11.25Z"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

<script setup lang="ts">
defineProps<{
  name: 'schedule' | 'leagues' | 'calculator' | 'profile' | 'info'
}>()
</script>

<style scoped>
.nav-tab-svg {
  display: block;
}
</style>
