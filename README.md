# 🪪 KYC Document Verifier

AI se document verify karo — upload karo Aadhaar/PAN/Passport, aur ye batayega
ki document genuine lag raha hai, aur agar mismatch ya quality issue hai to
**flag for manual review** kar dega.

## Kaise kaam karta hai

1. Aap select karte ho: "mujhe Aadhaar expect hai"
2. User document upload karta hai (image ya PDF)
3. Google Gemini (free, vision-capable AI) document ko dekhta hai aur batata hai:
   - Ye actually kaunsa document hai
   - Kya ye expected type se match karta hai
   - Koi quality issue hai kya (blurry, cropped, glare, etc.)
   - Manual review ke liye flag karna chahiye ya nahi

## Setup — Step by Step

### 1. Free Gemini API key lo

1. Jao: https://aistudio.google.com/app/apikey
2. Google account se sign in karo
3. "Create API Key" pe click karo
4. Key copy kar lo (kuch aisi dikhegi: `AIzaSy...`)

Ye **free** hai — koi credit card nahi chahiye, free tier mein daily kaafi
requests allowed hain.

### 2. Dependencies install karo

Terminal mein project folder ke andar:

```bash
pip install -r requirements.txt
```

### 3. API key configure karo

`.env.example` file ko copy karke `.env` banao, aur usme apni key paste karo:

```
GEMINI_API_KEY=AIzaSy...tumhari_actual_key_yaha
```

(Ya phir app khud API key box dikhayega agar `.env` set nahi kiya — wahin
paste kar sakte ho.)

### 4. App run karo

```bash
streamlit run app.py
```

Browser mein `http://localhost:8501` khul jayega.

## Use kaise karo

1. Dropdown se document type select karo (Aadhaar / PAN / Passport)
2. File upload karo
3. "Verify Document" button dabao
4. Result dekho — green (verified), yellow (mismatch), ya red (flagged)

## Project Structure

```
kyc-doc-verifier/
├── app.py              # Streamlit UI
├── verifier.py         # Core AI verification logic
├── requirements.txt    # Dependencies
├── .env.example         # API key template
└── README.md
```

## Isko aage kaise badha sakte ho

- Aur document types add karo (Voter ID, Driving License, etc.)
- Face-match verification add karo (Aadhaar photo vs selfie)
- Database mein results save karo audit trail ke liye
- Batch processing add karo (ek saath multiple documents check karna)
- OCR se actual data extract karo (naam, number, DOB) aur validate karo

## ⚠️ Important Disclaimer

Ye ek **learning/prototype project** hai. Real production KYC system ke liye
aur bhi cheezein chahiye:
- Liveness detection (fake photo vs real document differentiate karna)
- Tamper/forgery detection (Photoshop se edit kiya hua document pakadna)
- Government database se actual verification (jaise UIDAI API)
- Data privacy compliance (KYC data sensitive hai — encryption, secure storage,
  applicable data protection laws follow karna zaroori hai)
- Proper audit logging

Isko real users ke actual documents ke saath production mein use karne se
pehle in cheezon ko zaroor add karo.
