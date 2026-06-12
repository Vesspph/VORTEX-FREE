


# 📚 คู่มือการเชื่อมต่อระบบ VORTEX API (Integration Guide)

![Vortex Security](https://img.shields.io/badge/VORTEX-SECURITY_SYSTEM-orange?style=for-the-badge)
![API Status](https://img.shields.io/badge/API-v1.0.0-blue?style=for-the-badge)
![Database](https://img.shields.io/badge/Database-SQLite-green?style=for-the-badge)

คู่มือฉบับนี้จัดทำขึ้นเพื่อให้ผู้พัฒนาสามารถเชื่อมต่อระบบตรวจสอบคีย์ของ **VORTEX** เข้ากับแอปพลิเคชันรูปแบบต่างๆ เช่น **สคริปต์ Python, โปรแกรม C# (.NET/Windows Form/Unity), หรือหน้าเว็บไซต์ (JavaScript)** ได้อย่างปลอดภัยและมีประสิทธิภาพ

---

## 📌 สารบัญ (Table of Contents)
1. [ข้อมูลพื้นฐานเซิร์ฟเวอร์](#-ข้อมูลพื้นฐานเซิร์ฟเวอร์-server-configuration)
2. [รายละเอียด API Endpoints](#-รายละเอียด-api-endpoints)
    - [POST /verify (ตรวจสอบและผูกคีย์)](#1-post-verify-ตรวจสอบและผูกคีย์)
    - [GET /health (ตรวจสอบสถานะระบบ)](#2-get-health-ตรวจสอบสถานะเซิร์ฟเวอร์)
    - [GET /stats (ดูสถิติระบบ)](#3-get-stats-ดูสถิติรวมของระบบ)
3. [ตัวอย่างโค้ดการเชื่อมต่อ (Code Examples)](#-ตัวอย่างโค้ดการเชื่อมต่อ-code-examples)
    - [Python](#1-python-สำหรับสคริปต์ทั่วไป)
    - [C# (.NET / Unity)](#2-c-สำหรับ-windows-form--unity)
    - [JavaScript (Web Frontend / Node.js)](#3-javascript-สำหรับระบบเว็บ-frontend--nodejs)
4. [ข้อแนะนำด้านความปลอดภัย (Security Recommendations)](#-ข้อแนะนำด้านความปลอดภัย-security-recommendations)

---

## 🌐 ข้อมูลพื้นฐานเซิร์ฟเวอร์ (Server Configuration)

ในการเชื่อมต่อ แอปพลิเคชันของคุณจะต้องส่ง HTTP Request มายัง IP เซิร์ฟเวอร์ที่รันบอทดิสคอร์ดอยู่

* **Base URL:** `http://<IP_เซิร์ฟเวอร์ของคุณ>:30184` (เช่น `http://103.253.x.x:30184`)
* **Content-Type:** `application/json`
* **CORS Support:** รองรับการเรียกใช้งานข้ามโดเมนจากเว็บบราวเซอร์โดยตรง (`*`)

---

## 🛣️ รายละเอียด API Endpoints

### 1. `POST /verify` (ตรวจสอบและผูกคีย์)
ใช้สำหรับตรวจสอบความถูกต้องของคีย์ เช็ควันหมดอายุ และทำการผูกรหัสเครื่อง (HWID) ในการเปิดใช้งานครั้งแรก

**📥 Request Body (JSON):**
```json
{
  "key": "VORTEX-XXXX-XXXX",
  "hwid": "รหัสประจำเครื่องผู้ใช้ (เช่น CPU ID, MAC Address หรือ Motherboard Serial)"
}

```

**📤 Response (JSON):**

* **กรณีสำเร็จ (สถานะ 200 OK):**
* *เปิดใช้งานครั้งแรก (ผูก HWID สำเร็จ):*
```json
{
  "status": "success",
  "message": "ลงทะเบียนเครื่องสำเร็จ!",
  "expiration_date": "2026-12-31T23:59:59",
  "days_remaining": 200,
  "hwid_bound": true
}

```


* *เข้าใช้งานครั้งถัดไป (HWID ตรงกับในระบบ):*
```json
{
  "status": "success",
  "message": "ยินดีต้อนรับกลับ!",
  "expiration_date": "2026-12-31T23:59:59",
  "days_remaining": 200,
  "hwid_bound": true
}

```


* *กรณีคีย์ถาวร (Permanent Key):*
```json
{
  "status": "success",
  "message": "ยินดีต้อนรับกลับ!",
  "expiration_date": "permanent",
  "days_remaining": null,
  "hwid_bound": true
}

```




* **กรณีไม่สำเร็จ (สถานะ 400, 403, 404):**
* *ไม่พบข้อมูลคีย์:*
```json
{ "status": "fail", "message": "ไม่พบคีย์นี้ในระบบ!" }

```


* *คีย์ถูกระงับการใช้งาน (Revoked):*
```json
{ "status": "fail", "message": "คีย์นี้ถูก revoke แล้ว!" }

```


* *คีย์หมดอายุแล้ว:*
```json
{ "status": "fail", "message": "คีย์นี้หมดอายุแล้ว!", "expiration_date": "2026-01-01T00:00:00" }

```


* *คีย์ถูกใช้กับเครื่องอื่นไปแล้ว (HWID ไม่ตรง):*
```json
{ "status": "fail", "message": "คีย์นี้ถูกใช้ไปแล้วกับเครื่องอื่น!" }

```





---

### 2. `GET /health` (ตรวจสอบสถานะเซิร์ฟเวอร์)

ใช้ทดสอบว่า API Server กำลังทำงานอยู่ตามปกติหรือไม่

**📤 Response (JSON - 200 OK):**

```json
{
  "status": "ok",
  "message": "VORTEX API is running"
}

```

---

### 3. `GET /stats` (ดูสถิติรวมของระบบ)

เหมาะสำหรับดึงข้อมูลไปแสดงผลบนหน้าแดชบอร์ดของแอดมินหรือหน้าเว็บร้านค้า

**📤 Response (JSON - 200 OK):**

```json
{
  "status": "ok",
  "total_keys": 150,
  "active_keys": 120,
  "revoked_keys": 5,
  "bound_keys": 85
}

```

---

## 💻 ตัวอย่างโค้ดการเชื่อมต่อ (Code Examples)

### 1. Python (สำหรับสคริปต์ทั่วไป)

*ติดตั้งไลบรารีที่จำเป็นก่อนรัน:* `pip install requests`

```python
import requests
import uuid
import sys

def get_hwid():
    # ใช้ MAC Address เป็น HWID ตัวอย่าง (ในแอปจริงแนะนำให้ใช้ค่าที่แกะยากกว่านี้)
    return str(uuid.getnode())

def check_license(key):
    url = "http://YOUR_SERVER_IP:30184/verify"
    payload = {
        "key": key.strip(),
        "hwid": get_hwid()
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        data = response.json()
        
        if response.status_code == 200 and data.get("status") == "success":
            remaining = data.get("days_remaining")
            time_text = f"{remaining} วัน" if remaining is not None else "ถาวร (Permanent)"
            print(f"✅ [ผ่าน] {data.get('message')} | วันหมดอายุคงเหลือ: {time_text}")
            return True
        else:
            print(f"❌ [ปฏิเสธ] {data.get('message', 'เกิดข้อผิดพลาดไม่ทราบสาเหตุ')}")
            return False
            
    except requests.exceptions.RequestException:
        print("❌ ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ยืนยันสิทธิ์ได้")
        return False

if __name__ == "__main__":
    user_key = input("🔑 กรุณากรอกคีย์ใช้งานของคุณ: ")
    if not check_license(user_key):
        sys.exit(1)
        
    print("🚀 เริ่มรันโปรแกรมหลักของคุณตรงนี้...")

```

---

### 2. C# (สำหรับ Windows Form / Unity)

ตัวอย่างการเขียนฟังก์ชัน Async Request บนโปรแกรมฝั่ง Windows

```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

class VortexLicense
{
    private static readonly HttpClient client = new HttpClient();

    public static async Task<bool> VerifyLicense(string key, string hwid)
    {
        string url = "http://YOUR_SERVER_IP:30184/verify";
        
        // สร้าง JSON Payload
        string json = $"{{\\"key\\": \\"{key}\\", \\"hwid\\": \\"{hwid}\\"}}";
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        try
        {
            HttpResponseMessage response = await client.PostAsync(url, content);
            string responseString = await response.Content.ReadAsStringAsync();

            if (response.IsSuccessStatusCode && responseString.Contains("\\"status\\":\\"success\\""))
            {
                return true;
            }
            
            return false;
        }
        catch (Exception ex)
        {
            Console.WriteLine("Error: " + ex.Message);
            return false;
        }
    }
}

```

---

### 3. JavaScript (สำหรับระบบเว็บ Frontend / Node.js)

เหมาะสำหรับหน้าเว็บล็อกอิน หรือตรวจสอบการเข้าถึงคอนเทนต์พิเศษ

```javascript
const API_URL = "http://YOUR_SERVER_IP:30184/verify";

async function validateVortexKey(inputKey, userDeviceFingerprint) {
    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                key: inputKey,
                hwid: userDeviceFingerprint
            })
        });

        const result = await response.json();

        if (response.ok && result.status === "success") {
            console.log("✅ ยินดีต้อนรับ! ผ่านการตรวจสอบ:", result.message);
            return true;
        } else {
            console.error("❌ เข้าสู่ระบบไม่สำเร็จ:", result.message);
            alert(`ข้อผิดพลาด: ${result.message}`);
            return false;
        }
    } catch (error) {
        console.error("ไม่สามารถเชื่อมต่อ API ได้:", error);
        alert("ระบบเซิร์ฟเวอร์ขัดข้อง กรุณาลองใหม่อีกครั้งภายหลัง");
        return false;
    }
}

```

---

## 🔒 ข้อแนะนำด้านความปลอดภัย (Security Recommendations)

1. **การปกป้องซอร์สโค้ด (Code Obfuscation):** โปรแกรมที่ส่งให้ผู้ใช้ดาวน์โหลด มีโอกาสถูกส่องโค้ดหา IP API หรือตัดเงื่อนไขตรวจสอบออกได้ ควรใช้เครื่องมือเข้ารหัสโค้ด (เช่น PyArmor สำหรับ Python, ConfuserEx สำหรับ C#) ก่อนเผยแพร่ทุกครั้ง
2. **ปรับเปลี่ยนเป็น HTTPS:** แนะนำให้ตั้งค่า **Nginx** หรือ **Cloudflare** ทำเป็น Reverse Proxy เพื่อแปลงลิงก์เชื่อมต่อให้เป็นระบบความปลอดภัยแบบ `https://` ในอนาคต
3. **การดึงค่า HWID ถาวร:** หลีกเลี่ยงการใช้ค่าที่เปลี่ยนเองได้ง่าย เช่น IP Address ควรดึงค่าที่ไม่ซ้ำกันของฮาร์ดแวร์จริง เช่น **UUID ของเมนบอร์ด (Motherboard UUID)** หรือ **ซีเรียลนัมเบอร์ของ SSD** แทน

---
```
*พัฒนาและออกแบบระบบโดย VORTEX Security System*
```


