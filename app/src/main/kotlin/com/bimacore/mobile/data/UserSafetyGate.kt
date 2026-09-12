package com.bimacore.mobile.data

import com.bimacore.mobile.model.FileActionCard

/**
 * Gerbang Keamanan Pengguna (User Safety Gate).
 * Memastikan tindakan destruktif (seperti hapus berkas) tidak dapat dieksekusi
 * secara sembarangan tanpa persetujuan eksplisit dari Mas Bima.
 */
class UserSafetyGate {

    sealed class SafetyCheckResult {
        object SafeToExecute : SafetyCheckResult()
        data class RequiresConfirmation(val warningMessage: String) : SafetyCheckResult()
        data class Blocked(val reason: String) : SafetyCheckResult()
    }

    fun evaluate(card: FileActionCard): SafetyCheckResult {
        val action = card.actionType.uppercase()
        if (action == "DELETE") {
            if (card.isConfirmed) {
                return SafetyCheckResult.SafeToExecute
            }
            return SafetyCheckResult.RequiresConfirmation(
                "Peringatan: Berkas '${card.filePath}' akan dihapus permanen. Tindakan ini memerlukan persetujuan Mas Bima."
            )
        }

        if (action == "CLEAN") {
            if (card.isConfirmed) {
                return SafetyCheckResult.SafeToExecute
            }
            return SafetyCheckResult.RequiresConfirmation(
                "Peringatan: Pembersihan berkas sampah pada '${card.filePath}' memerlukan konfirmasi Mas Bima."
            )
        }

        // Aksi read/copy/move aman jika target valid
        return SafetyCheckResult.SafeToExecute
    }
}
