function DeleteTicket(ticketId) {
  fetch(`/delete_ticket/${ticketId}`, {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json'
      },
      credentials: 'same-origin'
  })
  .then(response => {
      if (response.ok) {
          return response.json();
      } else {
          throw new Error('Network response was not ok.');
      }
  })
  .then(data => {
      if (!data.message) throw new Error('The server did not confirm the ticket update.');
      location.reload();
  })
  .catch(error => {
      console.error('Failed to delete ticket: ', error);
      window.alert(error.message);
  });
}