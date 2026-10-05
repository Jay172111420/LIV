"use strict";

document.addEventListener("DOMContentLoaded", () => {
  console.log("Liv app loaded.");

  // Set footer year
  document.getElementById("year").textContent = new Date().getFullYear();
});
