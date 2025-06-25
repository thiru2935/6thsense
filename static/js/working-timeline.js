var timelineBlocks = document.querySelectorAll(".timeline-item");
var offset = 0.8;

function hideBlocks(blocks, offset) {
  blocks.forEach(function (block) {
    if (block.getBoundingClientRect().top > window.innerHeight * offset) {
      block
        .querySelectorAll(".timeline-icon, .timeline-content")
        .forEach(function (el) {
          el.classList.add("is-hidden");
        });
    }
  });
}

function showBlocks(blocks, offset) {
  blocks.forEach(function (block) {
    var icon = block.querySelector(".timeline-icon");
    if (
      block.getBoundingClientRect().top <= window.innerHeight * offset &&
      icon &&
      icon.classList.contains("is-hidden")
    ) {
      block
        .querySelectorAll(".timeline-icon, .timeline-content")
        .forEach(function (el) {
          el.classList.remove("is-hidden");
          el.classList.add("animate-it");
        });
    }
  });
}

// Ensure blocks are hidden first
hideBlocks(timelineBlocks, offset);

// Listen for scrolling to trigger animations
window.addEventListener("scroll", function () {
  requestAnimationFrame(() => showBlocks(timelineBlocks, offset));
});
