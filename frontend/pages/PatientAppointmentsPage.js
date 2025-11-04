export default {
  template: `
  <div class="container mt-4">
    <div class="row">
      <div class="col-md-12 text-center mb-4">        
        <h3>My Service Request Summary</h3>
      </div>
    </div>

    <div class="row justify-content-center">
      <div class="col-md-8">
        <div v-if="message" :class="'alert alert-' + category" role="alert">
          {{ message }}
        </div>

        <canvas id="serviceRequestsChart" height="200"></canvas>
      </div>
    </div>
  </div>
  `,

  data() {
    return {
      serviceRequestsChart: null,
      message: null,
      category: null,
    };
  },

  methods: {
    // Fetch the service request summary for the logged-in customer
    async fetchServiceRequestsCustomer() {
      try {
        // Get user claims (so we know the user_id)
        const claimsResponse = await fetch(`${location.origin}/get-claims`, {
          method: 'GET',
          headers: {
            'Authorization': 'Bearer ' + localStorage.getItem('token'),
            'Content-Type': 'application/json'
          }
        });

        if (!claimsResponse.ok) throw new Error('Failed to fetch user claims.');
        const claimData = await claimsResponse.json();
        const userId = claimData.claims?.user_id;

        if (!userId) {
          this.message = "Invalid user data. Please log in again.";
          this.category = "danger";
          return;
        }

        // Fetch summary data for that customer
        const serviceResponse = await fetch(`${location.origin}/customer/summary/service_requests/${userId}`, {
          method: 'GET',
          headers: {
            'Authorization': 'Bearer ' + localStorage.getItem('token'),
            'Content-Type': 'application/json'
          }
        });

        if (!serviceResponse.ok) throw new Error('Failed to fetch summary data.');
        const serviceData = await serviceResponse.json();

        if (!Array.isArray(serviceData) || !serviceData.length) {
          this.message = "No service request data found.";
          this.category = "info";
          return;
        }

        // Prepare chart data
        const labels = serviceData.map(item => item.date);
        const counts = serviceData.map(item => item.count);

        this.updateServiceRequestCustomerChart(labels, counts);
      } catch (error) {
        console.error('Error fetching service requests:', error);
        this.message = 'An unexpected error occurred while loading data.';
        this.category = 'danger';
      }
    },

    // Render bar chart with Chart.js
    updateServiceRequestCustomerChart(labels, data) {
      const ctx = document.getElementById('serviceRequestsChart').getContext('2d');
      if (this.serviceRequestsChart) this.serviceRequestsChart.destroy();

      this.serviceRequestsChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'Service Requests per Day',
            data,
            backgroundColor: 'rgba(54, 162, 235, 0.4)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'Request Count' } },
            x: { title: { display: true, text: 'Date' } }
          },
          plugins: {
            legend: { position: 'top' },
            tooltip: {
              callbacks: {
                label: tooltipItem => `Count: ${tooltipItem.raw}`
              }
            }
          }
        }
      });
    }
  },

  mounted() {
    this.fetchServiceRequestsCustomer();
  }
};
