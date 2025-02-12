<?php

{ 
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Registration Page</title>
    <link rel="stylesheet" href="style.css">
    <script>
        async function registerUser(event) {
            event.preventDefault();
            let form = document.forms["registerForm"];

            let response = await fetch ("../api/register_api.php", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(userData)
            });
            let result = await response.json();
            alert(result.message);
            if (result.success) window.location.href = "login.php";
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>Register</h1>
        <form name="registerForm" onsubmit="registerUser(event)">
            <input type="text" name="first_name" placeholder="First Name" required>
            <input type="text" name="last_name" placeholder="Last Name" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="tel" name="phone" placeholder="Phone Number" required>
            <input type="password" name="password" placeholder="Password" required>
            <input type="password" name="confirm_password" placeholder="Confirm Password" required>
            <br><br>
            <button type="submit">Register</button>
            <br><br>
            <p>Already have an account? <a href="login.php"> Login Here</a></p>
        </form>
    </div>
</body>
</html>

}
?>