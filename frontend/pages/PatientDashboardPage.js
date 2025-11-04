import Carousel from "../components/Carousel.js";

export default {
  components: { Carousel },

  data() {
    return {
      message: null,
      category: null,
      services: [],
      serviceRequests: [],
      serviceDict: {},
      profDict: {},
      serviceType: null,

      // Carousel slides for service categories
      carouselSlides: [
        {
          image: "/static/static/images/cleaning.jpg",
          alt: "Cleaning Services",
          link: "/customer/dashboard?service_type=cleaning",
          title: "Cleaning Services",
          description: "Keep your home or office spotless with our professional cleaning services.",
        },
        {
          image: "/static/static/images/plumber.jpg",
          alt: "Plumbing Services",
          link: "/customer/dashboard?service_type=plumbing",
          title: "Plumbing Services",
          description: "Fix leaks and plumbing issues with our experienced plumbers.",
        },
        {
          image: "/static/static/images/electrical.jpg",
          alt: "Electrical Services",
          link: "/customer/dashboard?service_type=electrical",
          title: "Electrical Services",
          description: "Get reliable electrical services for your home or office needs.",
        },
        {
          image: "/static/static/images/painting.jpg",
          alt: "Painting Services",
          link: "/customer/dashboard?service_type=painting",
          title: "Painting Services",
          description: "Beautify your space with our expert painting services.",
        },
        {
          image: "/static/static/images/haircut.jpg",
          alt: "Haircut at Home Services",
          link: "/customer/dashboard?service_type=haircut",
          title: "Haircut at Home",
          description: "Get a professional haircut at the comfort of your home.",
        },
      ],
    };
  },

  mounted() {
    // Get query parameter (if user navigated via a carousel link)
    const queryParams = this.$route.query;
    if (queryParams.service_type) {
      this.serviceType = queryParams.service_type;
    }
    this.fetchServices();
  },

  watch: {
    // React to changes in the route query parameter (for carousel clicks)
    "$route.query.service_type"(newServiceType) {
      this.serviceType = newServiceType;
      this.fetchServices();
    },
  },

  methods: {
    // Fetch all services and customer’s service requests
    async fetchServices() {
      try {
        const apiUrl = this.serviceType
          ? `/customer/dashboard?service_type=${this.serviceType}`
          : "/customer/dashboard";

        const response = await fetch(apiUrl, {
          method: "GET",
          headers: {
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
        });

        if (!response.ok) throw new Error("Failed to fetch dashboard data");

        const data = await response.json();
        this.services = data.services || [];
        this.serviceRequests = data.service_requests || [];
        this.serviceDict = data.service_dict || {};
        this.profDict = data.prof_dict || {};

        this.message = null;
      } catch (error) {
        console.error("Error fetching services:", error);
        this.message = "Unable to load services. Please try again later.";
        this.category = "danger";
      }
    },

    // Create a new service request for the logged-in customer
    async createServiceRequest(serviceId) {
      try {
        const response = await fetch(`/customer/create_service_request/${serviceId}`, {
          method: "POST",
          headers: {
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
        });

        const data = await response.json();

        if (response.ok) {
          this.message = data.message || "Service request created successfully!";
          this.category = data.category || "success";
          this.fetchServices();
        } else {
          this.message = data.message || "Failed to create service request.";
          this.category = data.category || "danger";
        }
      } catch (error) {
        console.error("Error creating service request:", error);
        this.message = "An error occurred while processing your request.";
        this.category = "danger";
      }
    },

    // Close (mark completed) a service request
    async closeServiceRequest(serviceRequestId) {
      try {
        const response = await fetch(`/customer/close_service_request/${serviceRequestId}`, {
          method: "POST",
          headers: {
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
        });

        const data = await response.json();
        if (response.ok) {
          this.message = data.message || "Service request closed successfully.";
          this.category = "success";
          this.fetchServices();
        } else {
          this.message = data.message || "Failed to close service request.";
          this.category = "danger";
        }
      } catch (error) {
        console.error("Error closing service request:", error);
        this.message = "Error closing service request.";
        this.category = "danger";
      }
    },
  },

  template: `
  <div class="container mt-4">
    <div class="row mb-3">
      <div class="col-md-12 text-center">
        <h3>Customer Dashboard</h3>
        <div v-if="message" :class="'alert alert-' + category" role="alert">
          {{ message }}
        </div>
      </div>
    </div>

    <!-- Carousel Section -->
    <Carousel :slides="carouselSlides" carousel-id="serviceCarousel" />

    <!-- Services Table -->
    <h4 class="mt-5">Available Services</h4>
    <table class="table table-striped mt-2">
      <thead>
        <tr>
          <th>Service Name</th>
          <th>Description</th>
          <th>Price</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="service in services" :key="service.id">
          <td>{{ service.name }}</td>
          <td>{{ service.description }}</td>
          <td>₹{{ service.price }}</td>
          <td>
            <button 
              @click="createServiceRequest(service.id)" 
              class="btn btn-primary btn-sm">
              Request
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Service History Table -->
    <h4 class="mt-5">Service History</h4>
    <table class="table table-bordered table-hover mt-2">
      <thead>
        <tr>
          <th>Service Name</th>
          <th>Professional</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="serviceRequest in serviceRequests" :key="serviceRequest.id">
          <td>{{ serviceDict[serviceRequest.service_id]?.name || 'N/A' }}</td>
          <td>{{ profDict[serviceRequest.professional_id]?.full_name || 'N/A' }}</td>
          <td>{{ serviceRequest.service_status }}</td>
          <td>
            <button
              v-if="serviceRequest.service_status !== 'completed'"
              @click="closeServiceRequest(serviceRequest.id)"
              class="btn btn-success btn-sm">
              Close
            </button>
            <span v-else class="text-muted">Closed</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  `,
};
