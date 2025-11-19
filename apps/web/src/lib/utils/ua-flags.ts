export function setUAClasses() {
  const ua = navigator.userAgent || "";
  const isAndroid = /Android/i.test(ua);
  if (isAndroid) document.documentElement.classList.add("ua-android");
}
