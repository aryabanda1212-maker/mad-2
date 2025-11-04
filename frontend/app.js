import Navbar from "./components/Navbar.js";
import router from "./utils/router.js";

const app = new Vue({
  el: "#app",
  template: `
    <div> 
      <Navbar v-if="isAuthenticated" :userRole="userRole"></Navbar>
      <router-view></router-view>
    </div>
  `,
  components: { Navbar },
  router,
  data() {
    return {
      isAuthenticated: false,
      userRole: null,
    };
  },
  methods: {
    // Called after successful login
    login(role, token, redirect = null) {
      this.isAuthenticated = true;
      this.userRole = role;

      // Save JWT and user info
      localStorage.setItem("isAuthenticated", "true");
      localStorage.setItem("userRole", role);
      localStorage.setItem("token", token);

      // Redirect user to their dashboard or profile setup
      if (redirect) {
        this.$router.push("/" + redirect.replace("_", "/"));
      } else if (role === "admin") {
        this.$router.push("/admin/dashboard");
      } else if (role === "doctor") {
        this.$router.push("/doctor/dashboard");
      } else if (role === "patient") {
        this.$router.push("/patient/dashboard");
      } else {
        this.$router.push("/");
      }
    },

    logout() {
      this.isAuthenticated = false;
      this.userRole = null;
      localStorage.removeItem("isAuthenticated");
      localStorage.removeItem("userRole");
      localStorage.removeItem("token");
      this.$router.push("/");
    },

    checkAuthentication() {
      this.isAuthenticated = localStorage.getItem("isAuthenticated") === "true";
      this.userRole = localStorage.getItem("userRole");
    },

    handleWindowClose() {
      localStorage.removeItem("isAuthenticated");
      localStorage.removeItem("userRole");
      localStorage.removeItem("token");
    }
  },

  mounted() {
    this.checkAuthentication();

    // If not logged in, restrict access
    if (!this.isAuthenticated) {
      const openRoutes = ["/", "/login", "/register", "/admin/login"];
      if (!openRoutes.includes(this.$route.path)) {
        this.$router.replace("/");
      }
    }

    window.addEventListener("beforeunload", this.handleWindowClose);
  },

  beforeDestroy() {
    window.removeEventListener("beforeunload", this.handleWindowClose);
  }
});
