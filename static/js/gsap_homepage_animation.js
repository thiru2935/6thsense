document.addEventListener("DOMContentLoaded", function () {
  gsap.registerPlugin(ScrollTrigger, CustomEase);
  const tl = gsap.timeline();
  const abouttl = gsap.timeline({
    scrollTrigger: {
      trigger: document.querySelector("#gsap-about"),
      start: "top 80%",
      end: "+=300 bottom",
      markers: false,
      toggleActions: "play none resume none",
    },
  });
  const aboutusuptl = gsap.timeline({
    scrollTrigger: {
      trigger: document.querySelector("#gsap-aboutus"),
      start: "top 80%",
      end: "+=100 bottom",
      markers: false,
      toggleActions: "play none resume none",
    },
  });
  const aboutustl = gsap.timeline({
    scrollTrigger: {
      trigger: ".aboutus2",
      start: "-=50 80%",
      end: "+=100 bottom",
      markers: false,
      toggleActions: "play none resume none",
    },
  });
  const forwhomtl=gsap.timeline({
    scrollTrigger:{
      trigger:".audience-section",
      start:"top 80%",
      end:"+=100 bottom",
      markers:false,
      toggleActions:"play none reset none",
    },
  });
  const securitysectiontl=gsap.timeline({
    scrollTrigger:{
      trigger:".security-section",
      start:"-=300 80%",
      end:"+=100 bottom",
      markers:false,
      toggleActions:"play none reset none",
    },
  });
  const servicestl = gsap.timeline({
    scrollTrigger: {
      trigger: document.querySelector("#gsap-services"),
      start: "+=200 80%",
      end: "bottom bottom",
      markers: false,
      toggleActions: "play none reset none",
    },
  });
  const workingheadtl = gsap.timeline({
    scrollTrigger: {
      trigger: document.querySelector("#gsap-working"),
      start: "top 80%",
      end: "bottom bottom",
      markers: false,
      scrub: 1,
      toggleActions: "play none resume none",
    },
  });
  const advantagestl = gsap.timeline({
    scrollTrigger: {
      trigger: ".advantages",
      start: "top 80%",
      end: "bottom bottom",
      markers: false,
      toggleActions: "play none resume none",
    },
  });
  const testimonialtl = gsap.timeline({
    scrollTrigger: {
      trigger: ".testimonials-main",
      start: "top 80%",
      end: "bottom bottom",
      markers: false,
      toggleActions: "play none resume none",
    },
  });
  const contactustl = gsap.timeline({
    scrollTrigger: {
      trigger: ".contact-section",
      start: "top 80%",
      end: "bottom bottom",
      markers: false,
      toggleActions: "play none reset none",
    },
  });

  //hero section video animation
  tl.fromTo(
    ".herovideo-animation",
    { scaleX: 0 },
    {
      scaleX: 1,
      duration: 2,
      ease: "cubic-bezier(0.390, 0.575, 0.565, 1.000)",
    }
  );

  //logo animation
  if (document.querySelector(".logo")) {
    tl.fromTo(
      ".logo",
      { y: "-100%", opacity: 0 },
      {
        y: "0%",
        opacity: 1,
        duration: 1,
        stagger: 0.2,
        ease: "power2.out",
      }
    );
  }

  //navbar animation
  if (document.querySelector(".gsap-navbarleft")) {
    tl.fromTo(
      ".gsap-navbarleft",
      { x: "-100%", opacity: 0 },
      {
        x: "0%",
        opacity: 1,
        duration: 0.8,
        stagger: 0.2,
        ease: "power2.out",
      }
    );
  }
  if (document.querySelector(".gsap-navbarright")) {
    tl.fromTo(
      ".gsap-navbarright > *",
      { x: "100%", opacity: 0 },
      { x: "0%", opacity: 1, duration: 1, ease: "power2.out", stagger: 0.2 }
    );
  }

  //herosection animation
  if (document.querySelector(".gsap-herosectionhead")) {
    const split = new SplitType(".gsap-herosectionhead", { types: "lines" });
    tl.from(split.lines, {
      opacity: 0,
      scaleY: 0.5,
      transformOrigin: "top",
      stagger: 0.5,
      duration: 1,
      ease: "power3.inout",
    });
  }

  if (document.querySelector(".gsap-herosectiontext")) {
    const herotext = new SplitType(".gsap-herosectiontext", { types: "lines" });
    tl.from(herotext.lines, {
      opacity: 0,
      y: 30,
      stagger: 0.3,
      duration: 1,
      ease: "power3.out",
    });
  }

  //hero section button animation
  if (document.querySelector(".gsap-herosectionbutton")) {
    tl.fromTo(
      ".gsap-herosectionbutton",
      { y: 500, opacity: 0, ease: "power2.in" },
      {
        y: 0,
        opacity: 1,
        duration: 1.1,
        ease: "bounce.out",
      },
      "-=2"
    );
  }

  //about scroll animation
  abouttl.fromTo(
    ".aboutspan1",
    { scaleX: 0, transformOrigin: "0% 0%", opacity: 1 },
    {
      scaleX: 1,
      transformOrigin: "0% 0%",
      opacity: 1,
      duration: 0.4,
      ease: "cubic-bezier(0.250, 0.460, 0.450, 0.940)",
    }
  );
  abouttl.fromTo(
    ".text__title",
    { scaleY: 0, transformOrigin: "100% 0%", opacity: 1 },
    {
      scaleY: 1,
      transformOrigin: "100% 0%",
      opacity: 1,
      duration: 0.3,
      ease: "cubic-bezier(0.250, 0.460, 0.450, 0.940)",
    },
    "+=1"
  );

  if (document.querySelector(".text__description")) {
    const abouttext = new SplitType(".text__description", { types: "lines" });
    abouttl.fromTo(
      abouttext.lines,
      {
        opacity: 0,
        transformOrigin: "0 0",
        rotateX: 180,
        perspective: 800,
      },
      {
        opacity: 1,
        rotateX: 0,
        duration: 0.5,
        stagger: 0.05,
        ease: "power2.out",
      }
    );
  }
  abouttl.fromTo(
    ".grid__container",
    {
      opacity: 0,
      scale: 2,
      filter: "blur(90px)",
      transformOrigin: "50% 50%",
    },
    {
      opacity: 1,
      scale: 1,
      filter: "blur(0px)",
      duration: 0.4,
      stagger: 0.05,
      ease: "power2.out",
    },
    "<"
  );

  //about us scroll animation
  aboutusuptl.fromTo(
    ".aboutus-up-span",
    { scaleX: 0, transformOrigin: "0% 0%", opacity: 1 },
    {
      scaleX: 1,
      transformOrigin: "0% 0%",
      opacity: 1,
      duration: 0.4,
      ease: "cubic-bezier(0.250, 0.460, 0.450, 0.940)",
    },
    0
  );
  aboutusuptl.fromTo(
    ".aboutus-up",
    { scaleX: 0, transformOrigin: "0% 0%" },
    {
      scaleX: 1,
      transformOrigin: "0% 0%",
      duration: 0.4,
      ease: "cubic-bezier(0.390, 0.575, 0.565, 1.000)",
    }
  );
  aboutusuptl.fromTo(
    ".aboutus-up-image",
    { scaleX: 0, transformOrigin: "100% 100%" },
    {
      scaleX: 1,
      transformOrigin: "100% 100%",
      duration: 0.4,
      ease: "cubic-bezier(0.390, 0.575, 0.565, 1.000)",
    }
  );
  if (document.querySelector(".aboutus-up-text")) {
    const aboutuptext = new SplitType(".aboutus-up-text", { types: "lines" });
    aboutusuptl.fromTo(
      aboutuptext.lines,
      { filter: "blur(12px)", opacity: 0 },
      {
        filter: "blur(0px)",
        opacity: 1,
        duration: 0.5,
        stagger: 0.05,
        ease: "easeInOut",
      }
    );
  }
  aboutustl.fromTo(
    ".center",
    { scaleY: 0, opacity: 1, transformOrigin: "center center" },
    { scaleY: 1, opacity: 1, duration: 0.7, ease: "easeInOut" },
    0
  );
  aboutustl.fromTo(
    ".aboutus-right-span",
    { scaleX: 0, transformOrigin: "0% 0%", opacity: 1 },
    {
      scaleX: 1,
      transformOrigin: "0% 0%",
      opacity: 1,
      duration: 0.4,
      ease: "cubic-bezier(0.250, 0.460, 0.450, 0.940)",
    }
  );
  aboutustl.fromTo(
    ".aboutus-left-span",
    { scaleX: 0, transformOrigin: "100% 100%", opacity: 1 },
    {
      scaleX: 1,
      transformOrigin: "100% 100%",
      opacity: 1,
      duration: 0.4,
      ease: "easeInOut",
    },
    "<"
  );
  aboutustl.fromTo(
    ".aboutus-right",
    { scaleX: 0, transformOrigin: "0% 0%" },
    {
      scaleX: 1,
      transformOrigin: "0% 0%",
      duration: 0.2,
      ease: "cubic-bezier(0.390, 0.575, 0.565, 1.000)",
    }
  );
  aboutustl.fromTo(
    ".aboutus-left",
    { scaleX: 0, transformOrigin: "100% 100%", opacity: 1 },
    {
      scaleX: 1,
      transformOrigin: "100% 100%",
      opacity: 1,
      duration: 0.2,
      ease: "easeInOut",
    },
    "<"
  );
  aboutustl.fromTo(
    ".aboutus-right-image",
    { scaleX: 0, transformOrigin: "100% 100%" },
    {
      scaleX: 1,
      transformOrigin: "100% 100%",
      duration: 0.3,
      ease: "cubic-bezier(0.390, 0.575, 0.565, 1.000)",
    }
  );
  aboutustl.fromTo(
    ".aboutus-left-image",
    { scaleX: 0, transformOrigin: "0% 0%", opacity: 1 },
    {
      scaleX: 1,
      transformOrigin: "0% 0%",
      opacity: 1,
      duration: 0.3,
      ease: "cubic-bezier(0.250, 0.460, 0.450, 0.940)",
    },
    "<"
  );
  if (document.querySelector(".aboutus-right-text")) {
    const aboutrighttext = new SplitType(".aboutus-right-text", { types: "lines" });
    aboutustl.fromTo(
      aboutrighttext.lines,
      { filter: "blur(12px)", opacity: 0 },
      {
        filter: "blur(0px)",
        opacity: 1,
        duration: 0.5,
        stagger: 0.05,
        ease: "easeInOut",
      }
    );
  }
  if (document.querySelector(".aboutus-left-text")) {
    const aboutlefttext = new SplitType(".aboutus-left-text", { types: "lines" });
    aboutustl.fromTo(
      aboutlefttext.lines,
      { filter: "blur(12px)", opacity: 0 },
      {
        filter: "blur(0px)",
        opacity: 1,
        duration: 0.5,
        stagger: 0.05,
        ease: "easeInOut",
      },
      "<"
    );
  }
  //for-whom section
  forwhomtl.fromTo(
  ".section-header",
  { z: -80, opacity: 0 },
  { z: 0, opacity: 1, duration: 0.4, ease: "easeInOut" },'>'
  );
  forwhomtl.fromTo(
    ".forwhom-card",
    {
      scale: 0,
      opacity: 1,
      transformOrigin: "50% 100%",
    },
    {
      scale: 1,
      opacity: 1,
      duration: 0.3,
      ease: "cubic-bezier(0.250, 0.460, 0.450, 0.940)",
    }
  );
  //security-section
  securitysectiontl.fromTo(
    ".security-section",
    {
      scale: 0,
      opacity: 1,
      transformOrigin: "50% 100%",
    },
    {
      scale: 1,
      opacity: 1,
      duration: 0.3,
      ease: "cubic-bezier(0.250, 0.460, 0.450, 0.940)",
    }
  );
  //services animation
  gsap.fromTo(
    ".services-span",
    { scaleY: 0, opacity: 1, transformOrigin: "100% 0%" },
    { scaleY: 1, opacity: 1, duration: 0.3, ease: "easeInOut" }
  );
  if (document.querySelector(".services-head")) {
    const serviceshead = new SplitType(".services-head", { types: "chars" });
    gsap.fromTo(
      serviceshead.chars,
      { scaleX: 0, opacity: 1, transformOrigin: "0% 0%" },
      { scaleX: 1, opacity: 1, duration: 0.2, ease: "easeInOut" }
    );
  }
  servicestl.fromTo(
    ".box1",
    { opacity: 0, scale: 0, transformOrigin: "50% 50%" },
    { opacity: 1, scale: 1, duration: 1, ease: "easeInOut" }
  );
  servicestl.fromTo(
    ".serviceboxspan1",
    { scaleX: 0, opacity: 1, transformOrigin: "50% 50%" },
    { scaleX: 1, opacity: 1, duration: 0.5, ease: "easeInOut" }
  );
  servicestl.fromTo(
    ".serviceboxhead1",
    { scaleY: 0, opacity: 1, transformOrigin: "0% 100%" },
    { scaleY: 1, opacity: 1, duration: 0.3, ease: "easeInOut" }
  );
  servicestl.fromTo(
    ".serviceboxtext1",
    { scaleY: 0, opacity: 1, transformOrigin: "100% 0%" },
    { scaleY: 1, opacity: 1, duration: 0.3, ease: "easeInOut" },
    "<"
  );
  servicestl.fromTo(
    ".box2",
    { z: -80, opacity: 0 },
    { z: 0, opacity: 1, duration: 0.6, stagger: 0.1, ease: "easeInOut" }
  );
  servicestl.fromTo(
    ".serviceboxspan2",
    { scaleX: 0, opacity: 1, transformOrigin: "50% 50%" },
    { scaleX: 1, opacity: 1, duration: 0.5, ease: "easeInOut" }
  );
  servicestl.fromTo(
    ".serviceboxhead2",
    { scaleY: 0, opacity: 1, transformOrigin: "0% 100%" },
    { scaleY: 1, opacity: 1, duration: 0.3, ease: "easeInOut" }
  );
  servicestl.fromTo(
    ".serviceboxtext2",
    { scaleY: 0, opacity: 1, transformOrigin: "100% 0%" },
    { scaleY: 1, opacity: 1, duration: 0.3, ease: "easeInOut" },
    "<"
  );
  servicestl.fromTo(
    ".nav-arrow",
    { opacity: 0, scale: 0, transformOrigin: "50% 50%" },
    { opacity: 1, scale: 1, duration: 1, ease: "easeInOut" }
  );

  //working animation
  workingheadtl.fromTo(
    ".workinghead-span",
    { scaleY: 0, opacity: 1, transformOrigin: "100% 0%" },
    { scaleY: 1, opacity: 1, duration: 0.3, ease: "easeInOut" }
  );
  if (document.querySelector(".working-header")) {
    const workinghead = new SplitType(".working-header", { types: "chars" });
    workingheadtl.fromTo(
      workinghead.chars,
      { scaleX: 0, opacity: 1, transformOrigin: "0% 0%" },
      { scaleX: 1, opacity: 1, duration: 0.2, ease: "easeInOut" }
    );
  }
  gsap.to(
    "#timeline",
    {
      "--timeline-height": "100%",
      opacity: 1,
      ease: "power2.out",
      scrollTrigger: {
        trigger: "#timeline",
        start: "top 80%",
        end: "bottom bottom",
        markers: false,
        scrub: 1,
        toggleActions: "play none reset none",
        ease: "power2.in",
      },
    },
    0
  );

  //advantages animation
  advantagestl.fromTo(
    ".advantages-card",
    {
      opacity: 0,
      transformOrigin: "50% 0%",
      rotateX: -90,
      perspective: 800,
    },
    {
      opacity: 1,
      rotateX: 0,
      duration: 1,
      ease: "power2.out",
      stagger: 0.5,
      onUpdate: function () {
        gsap.set(".boingInUp", {
          transformPerspective: 800,
        });
      },
    }
  );

  //testimonials section
  CustomEase.create("scaleInVerCenter", "0.250, 0.460, 0.450, 0.940");
  testimonialtl.from(".testimonials", {
    duration: 0.5,
    scaleY: 0,
    ease: "scaleInVerCenter",
  });
  CustomEase.create("fadeInEase", "0.390, 0.575, 0.565, 1.000");
  testimonialtl.from(".testimonials-inner", {
    duration: 1,
    opacity: 0,
    stagger: 0.2,
    ease: "fadeInEase",
  });
  CustomEase.create("ellipticEase", "0.250, 0.460, 0.450, 0.940");
  contactustl.from(".brand", {
    duration: 0.7,
    x: -800,
    rotateY: 30,
    scale: 0,
    transformOrigin: "-100% 50%",
    opacity: 0,
    ease: "ellipticEase",
    onComplete: function () {
      gsap.set(this.targets(), { transformOrigin: "1800px 50%" });
    },
  });
  contactustl.from(".contact", {
    duration: 0.6,
    x: 800,
    rotation: 540,
    opacity: 0,
    ease: "power1.out",
  });
  contactustl.from("#contact-form", {
    duration: 0.7,
    scale: 2,
    filter: "blur(4px)",
    opacity: 0,
    stagger: 0.5,
    ease: "power1.inOut",
  });
});