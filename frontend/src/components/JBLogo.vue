<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 100 100"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <!-- Dark Styled Background (Square for B-focus) -->
    <rect width="100" height="100" rx="16" fill="#2D2D2D" />

    <!-- White Stylized 'B' Base -->
    <path
      d="M25 20 H65 C80 20 80 45 65 45 C80 45 80 70 65 70 H25 V20 Z
         M37 30 V40 H60 Q 65 40 60 30 H37 Z
         M37 50 V60 H60 Q 65 60 60 50 H37 Z"
      fill="white"
      fill-rule="evenodd"
    />

    <!-- Orange Lightning Bolt Integrated INSIDE 'B' -->
    <path
      d="M50 30 L40 50 H55 L40 75 L60 45 H45 L55 30 Z"
      fill="#FF7F11"
      :style="{ filter: 'drop-shadow(0 0 2px rgba(0,0,0,0.5))' }"
    />
  </svg>
</template>

<script setup>
defineProps({
  size: {
    type: [Number, String],
    default: 48
  }
});
</script>
