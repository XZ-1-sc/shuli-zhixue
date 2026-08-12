import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "./styles.css";
import "./reference.css";
import "./auth.css";
import "./teacher.css";

import { useUserStore } from "./stores/user";

async function bootstrap() {
  const pinia = createPinia();
  const app = createApp(App);
  app.use(pinia);
  const user = useUserStore(pinia);
  await user.hydrateSession();
  app.use(router);
  await router.isReady();
  app.mount("#app");
}

bootstrap();
