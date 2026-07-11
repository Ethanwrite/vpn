/*
 * Copyright © 2017-2023 WireGuard LLC. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */
package org.amnezia.awg.configStore

import android.content.Context
import android.util.Log
import org.amnezia.awg.R
import org.amnezia.awg.config.BadConfigException
import org.amnezia.awg.config.Config
import java.io.File
import java.io.FileInputStream
import java.io.FileNotFoundException
import java.io.FileOutputStream
import java.io.IOException
import java.nio.charset.StandardCharsets
import java.util.concurrent.ConcurrentHashMap

/**
 * Configuration store that uses a `awg-quick`-style file for each configured tunnel.
 */
class FileConfigStore(private val context: Context) : ConfigStore {
    private val inMemoryConfigs = ConcurrentHashMap<String, Config>()

    init {
        deleteLegacyManagedConfig()
    }

    @Throws(IOException::class)
    override fun create(name: String, config: Config): Config {
        Log.d(TAG, "Creating configuration for tunnel $name")
        if (isManaged(name)) {
            deleteLegacyManagedConfig()
            if (inMemoryConfigs.putIfAbsent(name, config) != null)
                throw IOException(context.getString(R.string.config_file_exists_error, "$name.conf"))
            return config
        }
        val file = fileFor(name)
        if (!file.createNewFile())
            throw IOException(context.getString(R.string.config_file_exists_error, file.name))
        FileOutputStream(file, false).use { it.write(config.toAwgQuickString().toByteArray(StandardCharsets.UTF_8)) }
        return config
    }

    @Throws(IOException::class)
    override fun delete(name: String) {
        Log.d(TAG, "Deleting configuration for tunnel $name")
        if (isManaged(name)) {
            inMemoryConfigs.remove(name)
            deleteLegacyManagedConfig()
            return
        }
        val file = fileFor(name)
        if (!file.delete())
            throw IOException(context.getString(R.string.config_delete_error, file.name))
    }

    override fun enumerate(): Set<String> {
        deleteLegacyManagedConfig()
        return context.fileList()
            .filter { it.endsWith(".conf") }
            .map { it.substring(0, it.length - ".conf".length) }
            .filterNot(::isManaged)
            .toSet()
    }

    private fun fileFor(name: String): File {
        return File(context.filesDir, "$name.conf")
    }

    @Throws(BadConfigException::class, IOException::class)
    override fun load(name: String): Config {
        if (isManaged(name)) {
            return inMemoryConfigs[name]
                ?: throw FileNotFoundException(context.getString(R.string.config_not_found_error, "$name.conf"))
        }
        FileInputStream(fileFor(name)).use { stream -> return Config.parse(stream) }
    }

    @Throws(IOException::class)
    override fun rename(name: String, replacement: String) {
        if (isManaged(name) || isManaged(replacement))
            throw IOException("The managed Xingsui tunnel cannot be renamed")
        Log.d(TAG, "Renaming configuration for tunnel $name to $replacement")
        val file = fileFor(name)
        val replacementFile = fileFor(replacement)
        if (!replacementFile.createNewFile()) throw IOException(context.getString(R.string.config_exists_error, replacement))
        if (!file.renameTo(replacementFile)) {
            if (!replacementFile.delete()) Log.w(TAG, "Couldn't delete marker file for new name $replacement")
            throw IOException(context.getString(R.string.config_rename_error, file.name))
        }
    }

    @Throws(IOException::class)
    override fun save(name: String, config: Config): Config {
        Log.d(TAG, "Saving configuration for tunnel $name")
        if (isManaged(name)) {
            deleteLegacyManagedConfig()
            inMemoryConfigs[name] = config
            return config
        }
        val file = fileFor(name)
        if (!file.isFile)
            throw FileNotFoundException(context.getString(R.string.config_not_found_error, file.name))
        FileOutputStream(file, false).use { stream -> stream.write(config.toAwgQuickString().toByteArray(StandardCharsets.UTF_8)) }
        return config
    }

    private fun isManaged(name: String): Boolean = name == MANAGED_TUNNEL_NAME

    private fun deleteLegacyManagedConfig() {
        val legacy = fileFor(MANAGED_TUNNEL_NAME)
        if (legacy.exists() && !legacy.delete()) {
            Log.e(TAG, "Unable to remove legacy managed tunnel configuration")
            throw IllegalStateException("Unable to remove legacy managed tunnel configuration")
        }
    }

    companion object {
        private const val TAG = "AmneziaWG/FileConfigStore"
        private const val MANAGED_TUNNEL_NAME = "xingsui"
    }
}
