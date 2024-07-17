import pywhatkit as kit

# Phone number should include the country code

phone_number = '+233505036932'
message = "Hi"
# Time in 24-hour format
hour = 5
minute = 19

# Send the WhatsApp message
kit.sendwhatmsg(phone_number, message, hour, minute)

print("Message sent successfully!")
